from datetime import timezone

from openai import AsyncOpenAI
from sqlalchemy import select, update

from bx24.bx_utils.parse_call_info import parse_call_info, build_call_summary
from db.models.bx24_deal import Bx24Deal
from db.models.bx_processed_call import BxProcessedCall
from settings import OPENAI_TOKEN, AI_PROXY, TRANSCRIBE_MODEL

from telegram.send_log import send_dev_telegram_log


class TranscribeClient:
    """Класс для работы с Whisper API (транскрибирование аудио)"""

    def __init__(self, api_key: str = OPENAI_TOKEN):
        self.client = AsyncOpenAI(api_key=api_key)
        # self.client = AsyncOpenAI(api_key=api_key, base_url=AI_PROXY)

    async def transcribe(
        self,
        audio_file_path: str,
        model: str = TRANSCRIBE_MODEL,
        language: str = "ru",
    ):
        """
        Возвращает объект транскрипта (ответ SDK).
        """
        try:
            # Откроем файл и НЕ закрываем его, пока не завершится await
            with open(audio_file_path, "rb") as f:
                kwargs = dict(
                    file=f,
                    model=model,
                    language=language,
                )

                transcript = await self.client.audio.transcriptions.create(**kwargs)
                return transcript

        except Exception as e:
            await send_dev_telegram_log(f'[TranscribeClient.transcribe]\nОшибка транскрибации: {e}')
            raise RuntimeError(f"Transcribe error: {type(e).__name__}: {e}") from e

    async def transcribe_calls_for_deal(self, session_maker, domain, deal_id, need_init=False):
        """
        Транскрибирует все новые звонки в сделке.
        Отправляет транскрибацию в виде комментария в таймлайне в сделке.
        """
        try:
            async with session_maker() as s:
                async with s.begin():
                    deal_obj: Bx24Deal = await Bx24Deal.get_or_create(s, deal_id=deal_id, domain=domain)
                    if need_init:
                        ok, conversation_ids, _ = await deal_obj.init_chatwoot(s)
                        if not ok or not conversation_ids:
                            return

            new_calls = await deal_obj.get_calls_since()
            if not new_calls:
                return

            await send_dev_telegram_log(
                f'[transcribe_calls_for_deal]\nНачат процесс транскрибации звонков в сделке!\nid:{deal_id}\nпортал:{domain}\n'
                f'количество звонков: {len(new_calls)}', 'DEV'
            )

            transcribed_results = []
            latest_call_dt = deal_obj.last_transcribed_call

            for call in new_calls:
                try:
                    info = parse_call_info(call)
                except Exception as e:
                    await send_dev_telegram_log(f"[transcribe_calls_for_deal]\nparse_call_info error: {e}")
                    continue

                call_id = info.id
                if not call_id:
                    continue

                async with session_maker() as s:
                    existing: BxProcessedCall | None = await s.scalar(
                        select(BxProcessedCall).where(
                            BxProcessedCall.portal == deal_obj.bx_portal,
                            BxProcessedCall.call_id == str(call_id),
                        )
                    )

                need_stt = not (existing and existing.transcribation)
                if need_stt:
                    result = await deal_obj.handle_new_call(call)
                    async with session_maker() as s:
                        async with s.begin():
                            if existing is None:
                                existing = BxProcessedCall(
                                    portal=deal_obj.bx_portal,
                                    deal_bx_id=deal_obj.bx_id,
                                    call_id=str(call_id),
                                    transcribation=result.get("transcribation"),
                                    error=result.get("error"),
                                    sent_to_bx=False,
                                )
                                s.add(existing)
                            else:
                                existing.transcribation = result.get("transcribation")
                                existing.error = result.get("error")
                else:
                    result = {
                        "call_id": call_id,
                        "subject": info.subject,
                        "direction": info.direction,
                        "status": info.status,
                        "start": info.start.isoformat() if info.start else None,
                        "end": info.end.isoformat() if info.end else None,
                        "duration": info.duration_human,
                        "transcribation": existing.transcribation if existing else None,
                        "stt": None,
                        "error": existing.error if existing else None,
                    }

                transcribed_results.append(result)

                if result.get("transcribation") and not (existing and existing.sent_to_bx):
                    try:
                        call_info_str: str = build_call_summary(result)
                        deal_obj.but.call_api_method(
                            "crm.timeline.comment.add",
                            {"fields": {"ENTITY_ID": deal_obj.bx_id, "ENTITY_TYPE": "deal", "COMMENT": call_info_str}},
                        )
                        await send_dev_telegram_log(
                            f"[transcribe_calls_for_deal]\nТранскрибация сохранена в комменты сделки!\nid:{deal_id}\nпортал:{domain}"
                        )
                        async with session_maker() as s:
                            async with s.begin():
                                await s.execute(
                                    update(BxProcessedCall)
                                    .where(
                                        BxProcessedCall.portal == deal_obj.bx_portal,
                                        BxProcessedCall.call_id == str(call_id),
                                    )
                                    .values(sent_to_bx=True)
                                )
                    except Exception as e:
                        await send_dev_telegram_log(f"[transcribe_calls_for_deal]\nОшибка при отправке комментария в сделку!\nid:{deal_id}\nпортал:{domain}"
                                                    f"\n\nERROR: {e})", 'ERROR')

                call_dt = info.start or info.end
                if call_dt and call_dt.tzinfo is None:
                    call_dt = call_dt.replace(tzinfo=timezone.utc)
                if call_dt and (latest_call_dt is None or call_dt > latest_call_dt):
                    latest_call_dt = call_dt

            if latest_call_dt:
                async with session_maker() as s:
                    async with s.begin():
                        await deal_obj.save_max_last_transcribed_call(s, latest_call_dt)

        except Exception as e:
            await send_dev_telegram_log(f'[transcribe_calls_for_deal]\nГлобальная ошибка при транскрибации звонков в сделке!\nERROR: {str(e)}', 'ERROR')
