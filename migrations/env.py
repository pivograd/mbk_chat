from __future__ import annotations
import asyncio, os, sys
from pathlib import Path
from logging.config import fileConfig
from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

# --- Пути, чтобы импорты settings и моделей работали при запуске из корня ---
ROOT = Path(__file__).resolve().parents[1]  # корень проекта
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# --- Импорты проекта ---
from settings import DATABASE_URL
from db.models.base import Base
from db.models import bx24_deal  # noqa: F401
from db.models import chatwoot_conversation  # noqa: F401
from db.models.bx_handler_process import BxHandlerProcess  # noqa: F401
from db.models.bx_processed_call import BxProcessedCall  # noqa: F401
from db.models.contact_routing import ContactRouting  # noqa: F401
from db.models.rr_cursor import RRCursor  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def get_url():
    # 1) -x db_url=...
    x = context.get_x_argument(as_dictionary=True)
    if "db_url" in x and x["db_url"]:
        return x["db_url"]
    # 2) alembic.ini
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    # 3) ettings.DATABASE_URL
    if DATABASE_URL:
        return DATABASE_URL
    raise RuntimeError("Не задан URL БД: укажи в alembic.ini, или settings.DATABASE_URL, или через -x db_url=...")

def run_migrations_offline():
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations():
    url = get_url()
    connectable: AsyncEngine = create_async_engine(url, poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def do_run_migrations(connection: Connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
