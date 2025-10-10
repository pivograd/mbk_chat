import traceback
from urllib.parse import parse_qs

from aiohttp import web

from chatwoot_api.chatwoot_client import ChatwootClient
from db.models.bx24_deal import Bx24Deal
from db.models.bx_handler_process import BxHandlerProcess
from telegram.send_log import send_dev_telegram_log


async def handle_deal_update_comments_to_chatwoot(request):
    """
    Обработчик обновления сделки BX24
    синхронизирует комменты из таймлайна сделки с приватными комментариями чата в chatwoot
    """
    try:
        raw_text = await request.text()
        parsed = parse_qs(raw_text)
        deal_id = parsed.get("data[FIELDS][ID]")
        domain = parsed.get("auth[domain]")
        # await send_dev_telegram_log(f'REQUEST TO [handle_deal_update_comments_to_chatwoot] deal id: {deal_id}')

        if not deal_id or not domain:
            await send_dev_telegram_log(f'[handle_deal_update_comments_to_chatwoot]\n нет id сделки или домена\nparsed_data: {parsed}', 'WARNING')
            return web.Response(text='Не передан домен или id сделки', status=400)

        deal_id = deal_id[0]
        domain = domain[0]
        event_code = f'{domain}:DEAL:{deal_id}:COMMENTS'

        session_maker = request.app["db_sessionmaker"]
        async with session_maker() as session:
            async with session.begin():
                is_process = await BxHandlerProcess.acquire(session, event_code)
                if not is_process:
                    return web.Response(text="Уже обрабатывается", status=200)
        try:
            async with session_maker() as session:
                async with session.begin():
                    deal_obj: Bx24Deal = await Bx24Deal.get_or_create(session, deal_id=int(deal_id), domain=domain)

            async with session_maker() as session:
                async with session.begin():
                    ok, conversation_id, cw_contact_id, = await deal_obj.init_chatwoot(session)
                    if not ok:
                        return web.Response(text="Сделка не связана с chatwoot", status=200)

            comments = await deal_obj.get_timeline_comments()
            comments.sort(key=lambda c: int(c["ID"]))

            last_id = deal_obj.last_sync_comment_id or 0
            new_comments = [c for c in comments if int(c["ID"]) > last_id]
            if not new_comments:
                return web.Response(text="OK", status=200)

            async with ChatwootClient() as cw:
                for c in new_comments:
                    comment_text = c.get('COMMENT')
                    await cw.send_message(
                        conversation_id,
                        f'Комментарий из сделки BX24:\n {comment_text}',
                        private=True
                    )

            max_id = int(new_comments[-1]["ID"])
            async with session_maker() as session:
                async with session.begin():
                    await deal_obj.save_max_last_sync_comment_id(session, max_id)

            return web.Response(text="OK", status=200)

        except Exception as e_inner:
            tb = traceback.format_exc()
            await send_dev_telegram_log(f'[handle_deal_update_comments_to_chatwoot]\n Ошибка при обновлении сделки: {tb}', 'ERROR')
            return web.Response(text=str(e_inner), status=500)
        finally:
            try:
                async with session_maker() as session:
                    async with session.begin():
                        await BxHandlerProcess.release(session, event_code)
            except Exception as e:
                await send_dev_telegram_log(
                    f'[handle_deal_update_comments_to_chatwoot] Ошибка при process.release()\nEVENT_CODE: {event_code}\n Error: {e}', 'ERROR')

    except Exception as e:
        tb = traceback.format_exc()
        await send_dev_telegram_log(f'[handle_deal_update_comments_to_chatwoot]\n Критическая ошибка: {tb}', 'ERROR')
        return web.Response(text=str(e), status=500)