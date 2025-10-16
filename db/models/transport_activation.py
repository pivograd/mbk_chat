import traceback

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from bx24.models.bitrix_user_token import Base
from settings import BOTS_CFG
from telegram.send_log import send_dev_telegram_log, safe_log


class TransportActivation(Base):
    __tablename__ = "transport_activation"

    inbox_id = sa.Column(sa.Integer, primary_key=True, unique=True)
    is_active = sa.Column(sa.Boolean, nullable=False, server_default=sa.text("true"))
    updated_at = sa.Column(sa.DateTime(timezone=True),server_default=func.now(), onupdate=func.now(), nullable=False)


async def bootstrap_transport_activation(session: AsyncSession):
    """
    Создаёт в таблице TransportActivation
    """
    try:
        await safe_log(f'[bootstrap_transport_activation]\nВошли!', 'DEV')
        inbox_ids = set()
        for agent_cfg in BOTS_CFG:
            for transport in agent_cfg.transports:
                inbox_id = transport.chatwoot.inbox_id
                try:
                    inbox_ids.add(inbox_id)
                except (TypeError, ValueError):
                    continue
        await safe_log(f'[bootstrap_transport_activation]\nВошли!3', 'DEV')
        if not inbox_ids:
            await safe_log(f'[bootstrap_transport_activation]\nПУстойreturn0!\nРот его возвращал.','DEV')
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