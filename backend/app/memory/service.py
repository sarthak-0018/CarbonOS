import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.memory.contracts import MemoryService, ProfileFact
from app.models import ProfileFact as ProfileFactRow


class PersistentMemoryService(MemoryService):
    """SQL-backed profile facts. Suggestions remain unconfirmed until explicitly accepted."""

    def __init__(self, session: Session):
        self.session = session

    def list_facts(self, user_id: str) -> list[ProfileFact]:
        rows = self.session.scalars(
            select(ProfileFactRow)
            .where(ProfileFactRow.profile_id == uuid.UUID(user_id))
            .order_by(ProfileFactRow.added_at.desc())
        )
        return [self._contract(row) for row in rows]

    def propose_fact(self, user_id: str, fact: ProfileFact) -> str:
        row = ProfileFactRow(
            profile_id=uuid.UUID(user_id),
            key=fact.key,
            value=fact.value,
            source=fact.source,
            confidence=Decimal(str(fact.confidence)) if fact.confidence is not None else None,
            confirmed=fact.confirmed,
            added_at=datetime.combine(fact.added_on, time.min, tzinfo=timezone.utc),
        )
        self.session.add(row)
        self.session.commit()
        return str(row.id)

    @staticmethod
    def _contract(row: ProfileFactRow) -> ProfileFact:
        return ProfileFact(
            key=row.key,
            value=row.value,
            source=row.source,
            confidence=float(row.confidence) if row.confidence is not None else None,
            added_on=row.added_at.date() if row.added_at else date.today(),
            confirmed=row.confirmed,
        )
