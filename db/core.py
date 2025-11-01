import asyncio

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncEngine,
)

from db.models.transcription_job import run_transcription_worker
from settings import DATABASE_URL

from db.models.bx24_deal import Bx24Deal  # noqa: F401
from db.models.chatwoot_conversation import ChatwootConversation  # noqa: F401
from db.models.bx_handler_process import BxHandlerProcess  # noqa: F401
from db.models.bx_processed_call import BxProcessedCall  # noqa: F401
from db.models.contact_routing import ContactRouting  # noqa: F401
from db.models.rr_cursor import RRCursor  # noqa: F401
from db.models.transport_activation import TransportActivation # noqa: F401
from db.models.bx_deal_cw_link import BxDealCwLink  # noqa: F401
from db.models.bx_contact_cw_map import  BxContactCwMap  # noqa: F401
from db.models.transcription_job import  TranscriptionJob  # noqa: F401

from db.models.transport_activation import bootstrap_transport_activation
from telegram.send_log import send_dev_telegram_log


def make_engine() -> AsyncEngine:
    return create_async_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=1800,
    )

async def init_db(app):
    try:
        engine = make_engine()
        app["db_engine"] = engine

        local_session = async_sessionmaker(bind=engine, expire_on_commit=False)
        app["db_sessionmaker"] = local_session

        Bx24Deal.configure_sessionmaker(local_session)

        async with local_session() as session:
            await bootstrap_transport_activation(session)
        await send_dev_telegram_log('[init_db]\nОтрабтал без ошибок\nВЕБ СЕРВИС ПЕРЕЗАПУЩЕН!', 'WARNING')
    except Exception as e:
        await send_dev_telegram_log(f'[init_db]\nОШИБКА\n {e}', 'ERROR')

async def close_db(app):
    engine: AsyncEngine = app["db_engine"]
    await engine.dispose()

async def setup_workers(app):
    app['transcription_worker'] = app.loop.create_task(run_transcription_worker(app))

async def _cleanup_workers(app):
    app['transcription_worker'].cancel()
    try:
        await app['transcription_worker']
    except asyncio.CancelledError:
        pass