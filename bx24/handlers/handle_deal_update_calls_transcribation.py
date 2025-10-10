import traceback
from urllib.parse import parse_qs

from aiohttp import web
from datetime import timezone

from sqlalchemy import select, update

from bx24.bx_utils.parse_call_info import build_call_summary, parse_call_info
from db.models.bx24_deal import Bx24Deal
from db.models.bx_handler_process import BxHandlerProcess
from db.models.bx_processed_call import BxProcessedCall
from telegram.send_log import send_dev_telegram_log


async def handle_deal_update_calls_transcribation(request):
    """
    Обработчик обновления сделки BX24
    Транскрибирует звонки в сделке, при наличии связанного диалога в chatwoot
    """
    try:
        raw_text = await request.text()
        parsed = parse_qs(raw_text)

        deal_id = (parsed.get("data[FIELDS][ID]") or [None])[0]
        domain = (parsed.get("auth[domain]") or [None])[0]

        if not deal_id or not domain:
            await send_dev_telegram_log('[handle_deal_update_calls_transcribation] нет id сделки или домена')
            return web.Response(text='Не передан домен или id сделки', status=400)

        event_code = f"{domain}:DEAL:{deal_id}:CALLS"
        session_maker = request.app["db_sessionmaker"]

        async with session_maker() as session:
            async with session.begin():
                acquired = await BxHandlerProcess.acquire(session, event_code)
        if not acquired:
            await send_dev_telegram_log('[handle_deal_update_calls_transcribation]\nУже обрабатывается')
            return web.Response(text="Уже обрабатывается", status=200)

        try:
            async with session_maker() as session:
                async with session.begin():
                    deal_obj: Bx24Deal = await Bx24Deal.get_or_create(session, deal_id=int(deal_id), domain=domain)

            async with session_maker() as session:
                async with session.begin():
                    ok, _, _ = await deal_obj.init_chatwoot(session)
                    if not ok:
                        return web.Response(text="Сделка не связана с chatwoot", status=200)

            new_calls = await deal_obj.get_calls_since()
            if not new_calls:
                return web.Response(text="OK", status=200)

            await send_dev_telegram_log(
                f'[handle_deal_update_calls_transcribation]\nНачат процесс транскрибации звонков\nid:{deal_id}\nдомен:{domain}'
                f'количество звонков: {len(new_calls)}\n ID диалога CW: {deal_obj.chatwoot_conversation_id}'
            )

            transcribed_results = []
            latest_call_dt = deal_obj.last_transcribed_call

            for call in new_calls:
                try:
                    info = parse_call_info(call)
                except Exception as e:
                    await send_dev_telegram_log(f"[handle_deal_update_calls_transcribation]\ncall: {call}\nparse_call_info error: {e}")
                    continue

                call_id = info.id
                if not call_id:
                    continue

                async with session_maker() as session:
                    existing: BxProcessedCall | None = await session.scalar(
                        select(BxProcessedCall).where(
                            BxProcessedCall.portal == deal_obj.bx_portal,
                            BxProcessedCall.call_id == str(call_id),
                        )
                    )

                need_stt = not (existing and existing.transcribation)
                if need_stt:
                    await send_dev_telegram_log(f'[handle_deal_update_calls_transcribation]\nТранскрибируем звонок: {info}')
                    result = await deal_obj.handle_new_call(call)
                    async with session_maker() as session:
                        async with session.begin():
                            if existing is None:
                                existing = BxProcessedCall(
                                    portal=deal_obj.bx_portal,
                                    deal_bx_id=deal_obj.bx_id,
                                    call_id=str(call_id),
                                    transcribation=result.get("transcribation"),
                                    error=result.get("error"),
                                    sent_to_bx=False,
                                )
                                session.add(existing)
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

                if not result.get("transcribation"):
                    continue

                if existing and existing.sent_to_bx:
                    continue

                try:
                    call_info_str: str = build_call_summary(result)
                    deal_obj.but.call_api_method(
                        "crm.timeline.comment.add",
                        {
                            "fields": {
                                "ENTITY_ID": deal_obj.bx_id,
                                "ENTITY_TYPE": "deal",
                                "COMMENT": call_info_str,
                            }
                        },
                    )
                    await send_dev_telegram_log(
                        f"[handle_deal_update_calls_transcribation] Добавлен комментарий в сделку с ID: {deal_obj.bx_id}"
                    )

                    async with session_maker() as session:
                        async with session.begin():
                            await session.execute(
                                update(BxProcessedCall)
                                .where(
                                    BxProcessedCall.portal == deal_obj.bx_portal,
                                    BxProcessedCall.call_id == str(call_id),
                                )
                                .values(sent_to_bx=True)
                            )


                except Exception as e:
                    await send_dev_telegram_log(f"[handle_deal_update_calls_transcribation]\nevent_code: {event_code}\nОшибка при отправке комментария в Битрикс: {e}")

                call_dt = info.start or info.end
                if call_dt and call_dt.tzinfo is None:
                    call_dt = call_dt.replace(tzinfo=timezone.utc)
                if call_dt and (latest_call_dt is None or call_dt > latest_call_dt):
                    latest_call_dt = call_dt

            if latest_call_dt:
                async with session_maker() as session:
                    async with session.begin():
                        await deal_obj.save_max_last_transcribed_call(session, latest_call_dt)

            return web.Response(text="OK", status=200)

        except Exception as e_inner:
            error_msg = str(e_inner)
            tb = traceback.format_exc()
            await send_dev_telegram_log(f'[handle_deal_update_calls_transcribation]\nevent_code: {event_code}\nОшибка в логике: {tb}')
            return web.Response(text=error_msg, status=500)

        finally:
            if acquired:
                try:
                    async with session_maker() as session:
                        async with session.begin():
                            await BxHandlerProcess.release(session, event_code)
                except Exception as rel_e:
                    await send_dev_telegram_log(
                        f'[handle_deal_update_calls_transcribation] Ошибка при release(): {rel_e}'
                    )

    except Exception as e:
        tb = traceback.format_exc()
        await send_dev_telegram_log(f'[handle_deal_update_calls_transcribation] Критическая ошибка: {tb}')
        return web.Response(text=str(e), status=500)
