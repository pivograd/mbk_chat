from datetime import datetime, timezone
from sqlalchemy import Integer, String, DateTime, UniqueConstraint, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from db.models.base import Base

class BxProcessedCall(Base):
    __tablename__ = "bx_processed_call"
    __table_args__ = (UniqueConstraint("portal", "call_id", name="uq_portal_call"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portal: Mapped[str] = mapped_column(String(255), nullable=False)
    deal_bx_id: Mapped[int] = mapped_column(Integer, nullable=False)
    call_id: Mapped[str] = mapped_column(String(128), nullable=False)

    transcribation: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    sent_to_bx: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
