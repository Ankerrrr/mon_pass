from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from quant_home.auth.models import Administrator, AdminSession
from quant_home.auth.passwords import verify_password


class InvalidCredentials(Exception):
    pass


class LoginRateLimited(Exception):
    pass


@dataclass(frozen=True)
class SessionToken:
    token: str
    csrf_token: str
    expires_at: datetime


class LoginThrottle:
    def __init__(
        self,
        max_failures: int = 5,
        window: timedelta = timedelta(minutes=15),
    ) -> None:
        self.max_failures = max_failures
        self.window = window
        self._failures: dict[tuple[str, str], deque[datetime]] = defaultdict(deque)

    def record_failure(self, username: str, client_ip: str, now: datetime) -> bool:
        key = (username.casefold(), client_ip)
        failures = self._failures[key]
        cutoff = now - self.window
        while failures and failures[0] <= cutoff:
            failures.popleft()
        failures.append(now)
        return len(failures) >= self.max_failures

    def clear(self, username: str, client_ip: str) -> None:
        self._failures.pop((username.casefold(), client_ip), None)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class AuthService:
    def __init__(
        self,
        db: Session,
        throttle: LoginThrottle | None = None,
        session_lifetime: timedelta = timedelta(hours=12),
    ) -> None:
        self.db = db
        self.throttle = throttle or LoginThrottle()
        self.session_lifetime = session_lifetime

    def login(self, username: str, password: str, client_ip: str) -> SessionToken:
        administrator = self.db.scalar(
            select(Administrator).where(Administrator.username == username)
        )
        now = datetime.now(UTC)
        if administrator is None or not verify_password(password, administrator.password_hash):
            if self.throttle.record_failure(username, client_ip, now):
                raise LoginRateLimited
            raise InvalidCredentials

        self.throttle.clear(username, client_ip)
        raw_token = secrets.token_urlsafe(32)
        raw_csrf_token = secrets.token_urlsafe(32)
        expires_at = now + self.session_lifetime
        self.db.add(
            AdminSession(
                token_hash=_digest(raw_token),
                administrator_id=administrator.id,
                csrf_token_hash=_digest(raw_csrf_token),
                expires_at=expires_at,
            )
        )
        self.db.commit()
        return SessionToken(raw_token, raw_csrf_token, expires_at)

    def resolve_session(self, raw_token: str) -> AdminSession | None:
        session = self.db.scalar(
            select(AdminSession)
            .options(joinedload(AdminSession.administrator))
            .where(AdminSession.token_hash == _digest(raw_token))
        )
        if session is None:
            return None
        expires_at = session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            self.db.delete(session)
            self.db.commit()
            return None
        return session

    def csrf_is_valid(self, session: AdminSession, raw_csrf_token: str) -> bool:
        return secrets.compare_digest(session.csrf_token_hash, _digest(raw_csrf_token))

    def refresh_csrf(self, session: AdminSession) -> str:
        raw_csrf_token = secrets.token_urlsafe(32)
        session.csrf_token_hash = _digest(raw_csrf_token)
        self.db.commit()
        return raw_csrf_token

    def logout(self, session: AdminSession) -> None:
        self.db.delete(session)
        self.db.commit()
