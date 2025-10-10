import traceback
from urllib.parse import parse_qs

from aiohttp import web

from db.models.bx24_deal import Bx24Deal
from db.models.bx_handler_process import BxHandlerProcess
from telegram.send_log import send_dev_telegram_log


async def handle_deal_change_stage(request):
    """
    Обработчик обновления сделки BX24
    Отслеживает стадию сделки, при её смене отправляет приватную заметку в диалог Chatwoot
    """
    try:
        raw_text = await request.text()
        parsed = parse_qs(raw_text)
        deal_id = parsed.get("data[FIELDS][ID]")
        domain = parsed.get("auth[domain]")

        if not deal_id or not domain:
            await send_dev_telegram_log(f'[handle_deal_change_stage]\n нет id сделки или домена\nparsed_data: {parsed}')
            return web.Response(text='Не передан домен или id сделки', status=400)

        deal_id = deal_id[0]
        domain = domain[0]
        event_code = f'{domain}:DEAL:{deal_id}:STAGE'

        session_maker = request.app["db_sessionmaker"]
        async with session_maker() as session:
            async with session.begin():
                acquired = await BxHandlerProcess.acquire(session, event_code)

        if not acquired:
            await send_dev_telegram_log(
                f'[handle_deal_change_stage]\nЗанято другим процессом\nEVENT_CODE: {event_code}')
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

            async with session_maker() as session:
                async with session.begin():
                    deal_obj: Bx24Deal = await Bx24Deal.get_or_create(session, deal_id=int(deal_id), domain=domain)
                    ok = await deal_obj.sync_deal_stage_to_chatwoot(session)
                    if ok:
                        await send_dev_telegram_log(f'[handle_deal_change_stage]\nПоменялась стадия сделки\nBX_ID:{deal_obj.bx_id}'
                                                    f'\nBX_PORTAL:{deal_obj.bx_portal}\nID диалога CW: {deal_obj.chatwoot_conversation_id}')

            return web.Response(text="OK" if ok else "SKIPPED", status=200)

        except Exception as e:
            tb = traceback.format_exc()
            await send_dev_telegram_log(f'[handle_deal_change_stage]\n Ошибка обработки: {tb}')
            return web.Response(text="Ошибка обработки", status=500)

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
        await send_dev_telegram_log(f'[handle_deal_change_stage]\n Критическая ошибка: {tb}')
        return web.Response(text=str(e), status=500)