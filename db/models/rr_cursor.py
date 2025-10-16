from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, TIMESTAMP, text

from db.models.base import Base


class RRCursor(Base):
    __tablename__ = "rr_cursor"
    id: Mapped[int] = mapped_column(primary_key=True)
    agent_code_and_kind: Mapped[str] = mapped_column(String(64), unique=True)  # f'{agent_code}:{kind}'
    last_index: Mapped[int] = mapped_column(Integer, default=-1, server_default=text("-1"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
