from sqlalchemy import Column, String, Boolean, DateTime, Text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from datetime import datetime, timezone

from db.models.base import Base


class BxHandlerProcess(Base):
    __tablename__ = "bx_handler_process"

    event_code = Column(String(255), primary_key=True, unique=True, index=True)
    is_running = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    error = Column(Text, nullable=True)

    @classmethod
    async def acquire(cls, session: AsyncSession, event_code: str) -> bool:
        """
        Попытка занять процесс для event_code.
        Возвращает True, если удалось захватить, иначе False.
        """
        now = datetime.now(timezone.utc)

        stmt = (
            insert(cls.__table__)
            .values(
                event_code=event_code,
                is_running=True,
                updated_at=now,
                error=None,
            )
            .on_conflict_do_update(
                index_elements=["event_code"],
                set_={
                    "is_running": True,
                    "updated_at": now,
                    "error": None,
                },
                where=(cls.is_running == False),
            )
            .returning(cls.is_running)
        )

        res = await session.execute(stmt)
        row = res.fetchone()
        return bool(row and row[0])

    @classmethod
    async def release(cls, session: AsyncSession, event_code: str, error: str | None = None):
        """
        Освободить процесс по коду.
        """
        await session.execute(
            update(cls)
            .where(cls.event_code == event_code)
            .values(
                is_running=False,
                updated_at=datetime.now(timezone.utc),
                error=error,
            )
        )
