from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from quant_home.auth.models import Administrator, AdminSession
from quant_home.auth.passwords import hash_password, verify_password


def sync_configured_admin(db: Session, username: str, password: str) -> bool:
    """Make the configured credentials authoritative for the single local admin."""
    administrators = list(db.scalars(select(Administrator).order_by(Administrator.username)))
    administrator = next((item for item in administrators if item.username == username), None)
    created = administrator is None and not administrators
    if created:
        administrator = Administrator(username=username, password_hash=hash_password(password))
        db.add(administrator)
        db.commit()
        return True
    if administrator is None and len(administrators) == 1:
        administrator = administrators[0]
    elif administrator is None:
        administrator = Administrator(username=username, password_hash=hash_password(password))
        db.add(administrator)
        db.commit()
        return True

    changed = False
    if administrator.username != username:
        administrator.username = username
        changed = True
    if not verify_password(password, administrator.password_hash):
        administrator.password_hash = hash_password(password)
        changed = True
    if changed:
        db.flush()
        db.execute(delete(AdminSession).where(AdminSession.administrator_id == administrator.id))
        db.commit()
    return changed
