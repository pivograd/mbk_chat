import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import Integer, String, DateTime, Text, Boolean, Index, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from db.models.base import Base
from openai_agents.transcribation_client import TranscribeClient
from telegram.send_log import send_dev_telegram_log


class TranscriptionJob(Base):
    __tablename__ = "transcription_job"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portal: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    deal_bx_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(16), default="new", nullable=False)  # new|running|done|retry
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)

    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


    __table_args__ = (
        Index(
            "uq_transcription_job_active",
            "portal",
            "deal_bx_id",
            unique=True,
            postgresql_where=(status.in_(["new", "running", "retry"])),
        ),
    )


async def enqueue_transcription_job(session: AsyncSession, portal: str, deal_bx_id: int) -> tuple[int, bool]:
    """
    Ставит задачу на транскрибацию звонков в сделке
    """
    try:
        existing = await session.scalar(
            select(TranscriptionJob).where(
                TranscriptionJob.portal == portal,
                TranscriptionJob.deal_bx_id == deal_bx_id,
                TranscriptionJob.status.in_(("new", "running", "retry")),
            )
        )
        if existing:
            return existing.id, False

        job = TranscriptionJob(
            portal=portal,
            deal_bx_id=deal_bx_id,
            status="new",
            attempt=0,
            next_run_at=datetime.now(timezone.utc),
        )
        session.add(job)
        await session.flush()
        return job.id, True
    except Exception as e:
        await send_dev_telegram_log(f'[enqueue_transcription_job]\nОшибки при создании задачи для транскрибации!\nerror: {e}')


CONCURRENCY = 3
LEASE_SEC = 1500

async def run_transcription_worker(app):
    sem = asyncio.Semaphore(CONCURRENCY)
    session_maker = app["db_sessionmaker"]

    async def handle_job(job_id: int):
        async with sem:
            try:
                # Обновляем статус/lease и берём свежие данные
                async with session_maker() as s:
                    async with s.begin():
                        job = await s.get(TranscriptionJob, job_id, with_for_update=True)
                        if not job or job.status not in ("new", "retry", "running"):
                            return
                        job.status = "running"
                        job.attempt += 1
                        job.locked_until = datetime.now(timezone.utc) + timedelta(seconds=LEASE_SEC)

                await TranscribeClient().transcribe_calls_for_deal(session_maker, job.portal, job.deal_bx_id)

                async with session_maker() as s:
                    async with s.begin():
                        job = await s.get(TranscriptionJob, job_id, with_for_update=True)
                        job.status = "done"
                        job.locked_until = None
                        job.last_error = None
                        job.updated_at = datetime.now(timezone.utc)
            except Exception as e:
                backoff_min = min(60, 2 ** min(job.attempt, 6))  # 1..64 мин
                async with session_maker() as s:
                    async with s.begin():
                        job = await s.get(TranscriptionJob, job_id, with_for_update=True)
                        job.status = "retry"
                        job.last_error = str(e)[:2000]
                        job.next_run_at = datetime.now(timezone.utc) + timedelta(minutes=backoff_min)
                        job.locked_until = None
                        job.updated_at = datetime.now(timezone.utc)
                await send_dev_telegram_log(f'[transcription_worker] job {job_id} error: {e}', 'ERROR')

    while True:
        picked = []
        try:
            async with session_maker() as s:
                async with s.begin():
                    rows = (await s.scalars(
                        select(TranscriptionJob.id)
                        .where(
                            TranscriptionJob.status.in_(("new", "retry")),
                            TranscriptionJob.next_run_at <= func.now(),
                        )
                        .order_by(TranscriptionJob.priority, TranscriptionJob.created_at)
                        .with_for_update(skip_locked=True)
                        .limit(CONCURRENCY * 2)
                    )).all()
                    picked = rows
        except Exception as e:
            await send_dev_telegram_log(f'[transcription_worker] fetch error: {e}', 'ERROR')

        if not picked:
            await asyncio.sleep(1.0)
            continue

        for job_id in picked:
            asyncio.create_task(handle_job(job_id))
