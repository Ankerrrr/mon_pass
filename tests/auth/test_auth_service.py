import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from quant_home.auth.models import Administrator
from quant_home.auth.passwords import hash_password, verify_password
from quant_home.auth.service import (
    AuthService,
    InvalidCredentials,
    LoginRateLimited,
    LoginThrottle,
)
from quant_home.db import Base


def test_password_digest_does_not_contain_plaintext():
    password = "correct horse battery staple"

    digest = hash_password(password)

    assert "correct horse" not in digest
    assert verify_password(password, digest)
    assert not verify_password("wrong", digest)


def test_fifth_bad_login_is_rate_limited():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(
            Administrator(
                username="admin",
                password_hash=hash_password("valid-password"),
            )
        )
        db.commit()
        service = AuthService(db, throttle=LoginThrottle(max_failures=5))

        for _ in range(4):
            with pytest.raises(InvalidCredentials):
                service.login("admin", "wrong", "192.168.1.20")

        with pytest.raises(LoginRateLimited):
            service.login("admin", "wrong", "192.168.1.20")
