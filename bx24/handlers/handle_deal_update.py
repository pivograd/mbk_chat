from urllib.parse import parse_qs

from aiohttp import web

from db.models.bx24_deal import Bx24Deal
from db.models.bx_handler_process import BxHandlerProcess
from db.models.transcription_job import enqueue_transcription_job
from telegram.send_log import send_dev_telegram_log


async def handle_deal_update(request):
    """
    Обработчик обновления сделки Bx24
    """
    try:
        raw_text = await request.text()
        parsed = parse_qs(raw_text)
        deal_id = parsed.get("data[FIELDS][ID]")
        domain = parsed.get("auth[domain]")

        if not deal_id or not domain:
            await send_dev_telegram_log(f'[handle_deal_update]\nНеккоректный запрос на обработчик обновления сделки!\nНет домена или deal_id\nparsed_data: {parsed}', 'ERROR')
            return web.Response(text='Не передан домен или id сделки', status=400)

        deal_id = deal_id[0]
        domain = domain[0]

        session_maker = request.app["db_sessionmaker"]
        event_code = f"{domain}:DEAL:{deal_id}"
        try:
            async with session_maker() as session:
                async with session.begin():
                    acquired = await BxHandlerProcess.acquire(session, event_code)
                    if not acquired:
                        await send_dev_telegram_log(f'[handle_deal_update]\nЗанято другим процессом\nevent_code: {event_code}', 'DEV')
                        return web.Response(text="Уже обрабатывается", status=200)
                    deal_obj: Bx24Deal = await Bx24Deal.get_or_create(session, deal_id=int(deal_id), domain=domain)
                    ok, conversation_ids, cw_contact_id = await deal_obj.init_chatwoot(session)
                    if not ok or not conversation_ids:
                        return web.Response(text="Сделка не связана с chatwoot", status=200)
                    # Синхронизация стадии сделки
                    await deal_obj.sync_deal_stage_to_chatwoot(session)
                    # Синхронизация комментов из таймлайна сделки
                    await deal_obj.sync_deal_timeline_comments_to_chatwoot(session)
                    # Ставим задачу на траснкрибацию звонков в сделке
                    await enqueue_transcription_job(session, portal=domain, deal_bx_id=int(deal_id))
                    return web.Response(text="OK", status=200)


        except Exception as e:
            await send_dev_telegram_log(f'[handle_deal_update]\nОшибка в обработчике сделки!\nevent_code: {event_code}\n\nERROR: {e}', 'ERROR')
            return web.Response(text='error', status=500)
        finally:
            try:
                async with session_maker() as session:
                    async with session.begin():
                        await BxHandlerProcess.release(session, event_code)
            except Exception as e:
                await send_dev_telegram_log(f'[handle_deal_update]\nОшибка при process.release()\nevent_code: {event_code}\n\nError: {e}','ERROR')

    except Exception as e:
        await send_dev_telegram_log(f'[handle_deal_update]\nКритическая ошибка при обновлении сделки!\n\nERROR: {e}', 'ERROR')
        return web.Response(text='error', status=500)