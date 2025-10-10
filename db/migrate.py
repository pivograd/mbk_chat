from alembic import command
from alembic.config import Config
from pathlib import Path
from settings import DATABASE_URL

def alembic_upgrade_head():
    ini_path = (Path(__file__).resolve().parents[1] / "alembic.ini").as_posix()
    cfg = Config(ini_path)
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    command.upgrade(cfg, "head")
