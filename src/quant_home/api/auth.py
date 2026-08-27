from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from quant_home.auth.models import Administrator, AdminSession
from quant_home.auth.service import (
    AuthService,
    InvalidCredentials,
    LoginRateLimited,
)
from quant_home.db import get_db


router = APIRouter(prefix="/auth", tags=["authentication"])
Database = Annotated[Session, Depends(get_db)]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=1024)


def _service(request: Request, db: Session) -> AuthService:
    return AuthService(db, throttle=request.app.state.login_throttle)


def require_session(request: Request, db: Database) -> AdminSession:
    cookie_name = request.app.state.settings.session_cookie_name
    raw_token = request.cookies.get(cookie_name)
    session = _service(request, db).resolve_session(raw_token) if raw_token else None
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return session


def require_admin(
    session: Annotated[AdminSession, Depends(require_session)],
) -> Administrator:
    return session.administrator


def require_csrf(
    request: Request,
    db: Database,
    session: Annotated[AdminSession, Depends(require_session)],
) -> AdminSession:
    token = request.headers.get("X-CSRF-Token", "")
    if not token or not _service(request, db).csrf_is_valid(session, token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
    return session


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response, db: Database):
    client_ip = request.client.host if request.client else "unknown"
    try:
        session_token = _service(request, db).login(
            payload.username,
            payload.password,
            client_ip,
        )
    except InvalidCredentials as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED) from exc
    except LoginRateLimited as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS) from exc

    settings = request.app.state.settings
    response.set_cookie(
        settings.session_cookie_name,
        session_token.token,
        expires=session_token.expires_at,
        httponly=True,
        secure=settings.https_enabled,
        samesite="strict",
        path="/",
    )
    return {
        "user": {"username": payload.username},
        "csrf_token": session_token.csrf_token,
        "expires_at": session_token.expires_at,
    }


@router.get("/me")
def current_user(
    administrator: Annotated[Administrator, Depends(require_admin)],
) -> dict[str, str]:
    return {"username": administrator.username}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Database,
    session: Annotated[AdminSession, Depends(require_csrf)],
) -> None:
    _service(request, db).logout(session)
    response.delete_cookie(
        request.app.state.settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=request.app.state.settings.https_enabled,
        samesite="strict",
    )
