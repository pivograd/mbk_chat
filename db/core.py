from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncEngine,
)
from settings import DATABASE_URL

from db.models.bx24_deal import Bx24Deal  # noqa: F401
from db.models.chatwoot_conversation import ChatwootConversation  # noqa: F401
from db.models.bx_handler_process import BxHandlerProcess  # noqa: F401
from db.models.bx_processed_call import BxProcessedCall  # noqa: F401
from db.models.contact_routing import ContactRouting  # noqa: F401
from db.models.rr_cursor import RRCursor  # noqa: F401
from db.models.transport_activation import TransportActivation, bootstrap_transport_activation  # noqa: F401

def make_engine() -> AsyncEngine:
    return create_async_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=1800,
    )

async def init_db(app):
    engine = make_engine()
    app["db_engine"] = engine

    local_session = async_sessionmaker(bind=engine, expire_on_commit=False)
    app["db_sessionmaker"] = local_session

    Bx24Deal.configure_sessionmaker(local_session)

    async with local_session() as session:
        await bootstrap_transport_activation(session)

async def close_db(app):
    engine: AsyncEngine = app["db_engine"]
    await engine.dispose()
