import traceback

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.models.base import Base
from telegram.send_log import safe_log


class TransportActivation(Base):
    __tablename__ = "transport_activation"

    inbox_id = sa.Column(sa.Integer, primary_key=True, unique=True)
    is_active = sa.Column(sa.Boolean, nullable=False, server_default=sa.text("true"))
    updated_at = sa.Column(sa.DateTime(timezone=True),server_default=func.now(), onupdate=func.now(), nullable=False)

    @classmethod
    async def set_active(cls, session: AsyncSession, inbox_id: int, active: bool) -> None:
        stmt = pg_insert(cls).values(
            inbox_id=inbox_id,
            is_active=active,
        ).on_conflict_do_update(
            index_elements=[cls.inbox_id],
            set_={
                "is_active": sa.literal(active),
                "updated_at": func.now(),
            },
        )
        await session.execute(stmt)
        await session.commit()

    @classmethod
    async def deactivate(cls, session: AsyncSession, inbox_id: int) -> None:
        await cls.set_active(session, inbox_id, False)

    @classmethod
    async def activate(cls, session: AsyncSession, inbox_id: int) -> None:
        await cls.set_active(session, inbox_id, True)

    @classmethod
    async def get_active_inboxes(cls, session: AsyncSession) -> list[int]:
        """
        """
        q = await session.execute(
            select(cls.inbox_id).where(cls.is_active.is_(True))
        )
        return [row[0] for row in q.all()]


async def bootstrap_transport_activation(session: AsyncSession):
    """
    Создаёт в таблице TransportActivation
    """
    try:
        inbox_ids = set()
        from settings import BOTS_CFG
        for agent_cfg in BOTS_CFG:
            for transport in agent_cfg.transports:
                inbox_id = transport.chatwoot.inbox_id
                try:
                    inbox_ids.add(inbox_id)
                except (TypeError, ValueError):
                    continue
        if not inbox_ids:
            await safe_log(f'[bootstrap_transport_activation]\nНет inbox_ids для выбора транспора!','WARNING')
            return

        # TODO здесь можно проверять активность инстансов, пока считаем, что при запуске все активные.
        rows = [{"inbox_id": iid, "is_active": True, "updated_at": func.now()} for iid in inbox_ids]
        stmt = (
            pg_insert(TransportActivation.__table__)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["inbox_id"])
        )
        await safe_log(f'[bootstrap_transport_activation]\nВошли4!', 'DEV')

        await session.execute(stmt)
        await session.commit()
        await safe_log(f'[bootstrap_transport_activation]\nАктивные транспорты сконфигурированы в БД!', 'DEV')
    except Exception as e:
        tb = traceback.format_exc()
        await safe_log(f'[bootstrap_transport_activation]\nКритическая ошибка!\nError: {tb}', 'ERROR')
        raise