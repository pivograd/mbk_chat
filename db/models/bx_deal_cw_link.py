from datetime import datetime
from typing import Sequence, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import Integer, String, DateTime, UniqueConstraint, Index, func, select, Boolean, text, desc, literal, \
    update

from db.models.base import Base
from settings import AGENT_TO_INBOX_IDS, PORTAL_AGENTS
from telegram.send_log import send_dev_telegram_log


class BxDealCwLink(Base):
    __tablename__ = "bx_deal_cw_link"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    bx_portal: Mapped[str] = mapped_column(String(255), nullable=False)
    bx_deal_id: Mapped[int] = mapped_column(Integer, nullable=False)

    cw_conversation_id: Mapped[int] = mapped_column(Integer, nullable=False)
    cw_inbox_id: Mapped[int] = mapped_column(Integer, nullable=False)
    cw_contact_id: Mapped[int] = mapped_column(Integer, nullable=False)

    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("bx_portal", "bx_deal_id", "cw_conversation_id", name="uq_link_portal_deal_conv"),
        Index("ix_link_cw_conversation_id", "cw_conversation_id"),
        Index("ix_link_bx_deal", "bx_portal", "bx_deal_id"),
        Index("uq_link_primary_per_deal", "bx_portal", "bx_deal_id", unique=True, postgresql_where=text("is_primary = true"))
    )

    @classmethod
    async def get_links_for_deal(cls, session: AsyncSession, portal: str, deal_id: int) -> Sequence["BxDealCwLink"]:
        """
        Возвращает связи сделки, отфильтрованные по списку допустимых inbox'ов агента
        """
        from db.models.bx24_deal import Bx24Deal

        # Вычисляем inboxы для текущей сделки
        deal = await session.scalar(
            select(Bx24Deal).where(
                Bx24Deal.bx_portal == portal,
                Bx24Deal.bx_id == int(deal_id),
            )
        )
        bx_funnel_id = deal.bx_funnel_id if deal else None
        agent_code = PORTAL_AGENTS.get(portal, {}).get(bx_funnel_id)
        agent_inboxes = AGENT_TO_INBOX_IDS.get(agent_code) or []

        q = select(cls).where(
            cls.bx_portal == portal,
            cls.bx_deal_id == deal_id,
        )

        # if agent_inboxes:
        #     q = q.where(cls.cw_inbox_id.in_(agent_inboxes))

        q = q.order_by(desc(cls.is_primary), desc(cls.created_at))

        return (await session.execute(q)).scalars().all()

    @classmethod
    async def get_selected_conversation_id(cls, session: AsyncSession, portal: str, deal_id: int) -> Optional[int]:
        """

        """
        q1 = select(cls.cw_conversation_id).where(
            cls.bx_portal == portal, cls.bx_deal_id == deal_id, cls.is_primary.is_(True)
        ).limit(1)
        row = (await session.execute(q1)).scalar_one_or_none()
        if row is not None:
            return row
        q2 = (
            select(cls.cw_conversation_id)
            .where(cls.bx_portal == portal, cls.bx_deal_id == deal_id)
            .order_by(desc(cls.created_at))
            .limit(1)
        )
        return (await session.execute(q2)).scalar_one_or_none()

    @classmethod
    async def set_primary_conversation( cls, session: AsyncSession, portal: str, deal_id: int, conversation_id: int) -> bool:
        """

        """
        exists_q = select(literal(True)).where(
            cls.bx_portal == portal,
            cls.bx_deal_id == deal_id,
            cls.cw_conversation_id == conversation_id,
        ).limit(1)
        if (await session.execute(exists_q)).scalar_one_or_none() is None:
            return False

        await session.execute(
            update(cls)
            .where(cls.bx_portal == portal, cls.bx_deal_id == deal_id, cls.is_primary.is_(True))
            .values(is_primary=False)
        )

        await session.execute(
            update(cls)
            .where(
                cls.bx_portal == portal,
                cls.bx_deal_id == deal_id,
                cls.cw_conversation_id == conversation_id,
            )
            .values(is_primary=True)
        )
        return True

    @classmethod
    async def get_deals_for_conversation(
            cls,
            session: AsyncSession,
            portal: str,
            conversation_id: int,
    ) -> Sequence["BxDealCwLink"]:
        q = select(cls).where(
            cls.bx_portal == portal,
            cls.cw_conversation_id == conversation_id,
        )

        q = q.order_by(desc(cls.is_primary), desc(cls.created_at))

        return (await session.execute(q)).scalars().all()

#TODO try except широкий в методах

async def link_deal_with_conversation(
    session: AsyncSession,
    bx_portal: str,
    bx_deal_id: int,
    cw_conversation_id: int,
    cw_inbox_id: int,
    cw_contact_id: int,
) -> None:
    stmt = pg_insert(BxDealCwLink).values(
        bx_portal=bx_portal,
        bx_deal_id=bx_deal_id,
        cw_conversation_id=cw_conversation_id,
        cw_inbox_id=cw_inbox_id,
        cw_contact_id=cw_contact_id,
    ).on_conflict_do_nothing(
        constraint="uq_link_portal_deal_conv"
    )
    await session.execute(stmt)


async def get_conversation_ids_for_deal(session: AsyncSession, bx_portal: str, bx_id: str):
    return await session.scalars(
        select(BxDealCwLink.cw_conversation_id).where(
            BxDealCwLink.bx_portal == bx_portal,
            BxDealCwLink.bx_deal_id == bx_id,
        )
    )
