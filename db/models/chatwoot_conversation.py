from typing import Optional

from sqlalchemy import UniqueConstraint, Integer, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base


class ChatwootConversation(Base):
    __tablename__ = "chatwoot_conversation"
    __table_args__ = (UniqueConstraint("chatwoot_id", name="uq_cw_chatwoot_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chatwoot_id: Mapped[int] = mapped_column(Integer, nullable=False)
    last_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # contact_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # deal_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bx_deal.id"), nullable=True)

    @staticmethod
    async def get_or_create(session: AsyncSession, chatwoot_id: int) -> "ChatwootConversation":
        """
        Находит запись по уникальному chatwoot_id.
        Если нет — создаёт. Защита от гонок через savepoint + перехват IntegrityError.
        """
        stmt = select(ChatwootConversation).where(ChatwootConversation.chatwoot_id == chatwoot_id)
        obj = await session.scalar(stmt)
        if obj:
            return obj

        async with session.begin_nested():
            obj = ChatwootConversation(chatwoot_id=chatwoot_id)
            session.add(obj)
            try:
                await session.flush()
            except IntegrityError:
                pass

        return await session.scalar(stmt)
