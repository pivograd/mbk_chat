from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, Boolean, UniqueConstraint, TIMESTAMP, text, select, and_
from db.models.base import Base
from utils.normalize_phone import normalize_phone


class ContactRouting(Base):
    __tablename__ = "contact_routing"
    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(32), index=True)
    agent_code: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(8))  # 'wa' | 'tg'
    inbox_id: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    __table_args__ = (
        UniqueConstraint('phone', 'agent_code', 'kind', name='uq_contact_agent_kind'),
    )


    @classmethod
    async def get_inboxes_id(cls, session: AsyncSession, phone: str, agent_code : str) -> list[int]:
        """
        Возвращает список inbox_id из contact_routing
        фильтр по (agent_code, phone)
        """
        inbox_ids: list[int] = []
        seen = set()

        def _extend(rows):
            for r in rows:
                iid = r[0]
                if iid not in seen:
                    inbox_ids.append(iid)
                    seen.add(iid)

        phone = normalize_phone(phone)
        stmt = (
            select(cls.inbox_id)
            .where(
                and_(
                    cls.phone == phone,
                    cls.agent_code == agent_code,
                )
            )
            .distinct()
        )
        res = await session.execute(stmt)
        _extend(res.all())

        return inbox_ids