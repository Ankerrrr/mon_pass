from sqlalchemy import create_engine

from quant_home.auth.bootstrap import sync_configured_admin
from quant_home.auth.models import Administrator
from quant_home.auth.passwords import hash_password, verify_password
from quant_home.db import Base, create_session_factory


def test_configured_credentials_update_the_existing_single_admin():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = create_session_factory(engine)
    with sessions() as db:
        db.add(Administrator(username="old-admin", password_hash=hash_password("old-password")))
        db.commit()
        assert sync_configured_admin(db, "new-admin", "new-password") is True
        administrator = db.query(Administrator).one()
        assert administrator.username == "new-admin"
        assert verify_password("new-password", administrator.password_hash)
        digest = administrator.password_hash
        assert sync_configured_admin(db, "new-admin", "new-password") is False
        assert administrator.password_hash == digest
