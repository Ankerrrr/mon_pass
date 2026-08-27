from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from quant_home.audit.models import AuditEvent


class AuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self, actor_id: UUID | None, action: str, subject_type: str,
        subject_id: str | None = None, metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            actor_id=actor_id, action=action, subject_type=subject_type,
            subject_id=subject_id, event_metadata=metadata or {},
        )
        self.db.add(event)
        self.db.commit()
        return event

    def list(self, limit: int = 100) -> list[AuditEvent]:
        return list(self.db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)))
