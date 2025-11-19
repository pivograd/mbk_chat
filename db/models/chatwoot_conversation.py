from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import UniqueConstraint, Integer, select, Boolean, DateTime
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
    last_client_message_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    agent_contact_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    next_meeting_datetime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    warmup_number: Mapped[int] = mapped_column(Integer, nullable=True)
    last_warmup_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

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

    def get_next_warmup_date(self) -> Optional[datetime]:
        """
        Возвращает дату следующей прогревающей рассылки, исходя из:
        - last_client_message_date — дата последнего сообщения клиента;
        - warmup_number — сколько рассылок уже было.

        Правила:
        - если рассылок не было (warmup_number is None или 0) -> +2 дня
        - если была 1 рассылка  -> +3 дня
        - если было 2 рассылки  -> +5 дней
        - если было 3 рассылки  -> +7 дней
        - если было 4 рассылки  -> +10 дней
        - если было 5 и больше  -> +14 дней
        """
        if self.last_client_message_date is None:
            if not self.last_message_id:
                raise Exception(f'Попытка посчитать дату рассылки для диалога без клиентских сообщений! conv_id: {self.chatwoot_id}')
            else:
                return None


        warmup_num = self.warmup_number or 0

        if warmup_num <= 0:
            days_to_add = 2
        elif warmup_num == 1:
            days_to_add = 3
        elif warmup_num == 2:
            days_to_add = 5
        elif warmup_num == 3:
            days_to_add = 7
        elif warmup_num == 4:
            days_to_add = 10
        else:
            days_to_add = 14

        return self.last_client_message_date + timedelta(days=days_to_add)
