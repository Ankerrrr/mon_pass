from fastapi.testclient import TestClient

from quant_home.config import Settings
from quant_home.main import create_app


def make_client() -> TestClient:
    settings = Settings(
        environment="test",
        database_url="sqlite+pysqlite:///:memory:",
        initial_admin_username="admin",
        initial_admin_password="valid-password",
    )
    return TestClient(create_app(settings))


def test_unauthenticated_current_user_is_rejected():
    with make_client() as client:
        response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_login_current_user_and_csrf_protected_logout():
    with make_client() as client:
        login = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "valid-password"},
        )

        assert login.status_code == 200
        assert login.json()["user"] == {"username": "admin"}
        csrf_token = login.json()["csrf_token"]
        cookie = login.headers["set-cookie"]
        assert "HttpOnly" in cookie
        assert "SameSite=strict" in cookie
        assert "Secure" not in cookie

        current_user = client.get("/api/auth/me")
        assert current_user.status_code == 200
        assert current_user.json() == {"username": "admin"}

        missing_csrf = client.post("/api/auth/logout")
        assert missing_csrf.status_code == 403

        logout = client.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert logout.status_code == 204
        assert client.get("/api/auth/me").status_code == 401


def test_authenticated_session_can_refresh_its_csrf_token():
    with make_client() as client:
        login = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "valid-password"},
        )
        old_token = login.json()["csrf_token"]

        refreshed = client.get("/api/auth/csrf")

        assert refreshed.status_code == 200
        new_token = refreshed.json()["csrf_token"]
        assert new_token != old_token
        assert "quant_home_csrf=" in refreshed.headers["set-cookie"]
        assert client.post(
            "/api/auth/logout", headers={"X-CSRF-Token": old_token}
        ).status_code == 403
        assert client.post(
            "/api/auth/logout", headers={"X-CSRF-Token": new_token}
        ).status_code == 204


def test_fifth_bad_api_login_is_rate_limited():
    with make_client() as client:
        for _ in range(4):
            response = client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "wrong"},
            )
            assert response.status_code == 401

        response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "wrong"},
        )

    assert response.status_code == 429
