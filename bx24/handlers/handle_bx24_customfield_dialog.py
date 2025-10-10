import json
from urllib.parse import parse_qsl, unquote
import traceback

import aiohttp_jinja2
from aiohttp import web

from chatwoot_api.chatwoot_client import ChatwootClient
from db.models.bx24_deal import Bx24Deal
from settings import but_map_dict
from telegram.send_log import send_dev_telegram_log
from utils.build_contact_info import build_contact_info


@aiohttp_jinja2.template("chat.html")
async def handle_bx24_customfield_dialog(request: web.Request):
    """
    Обработчик для отображения диалога Chatwoot в кастомном поле сделки BX24
    """
    try:
        raw_qs = unquote(request.query_string or "")
        params = dict(parse_qsl(raw_qs, keep_blank_values=True))
        domain = params.get("DOMAIN")

        form = await request.post()
        placement_options = json.loads(form.get("PLACEMENT_OPTIONS", '')) or {}
        entity_id = placement_options.get('ENTITY_DATA', {}).get('entityId')

        session_maker = request.app["db_sessionmaker"]
        async with session_maker() as session:
            async with session.begin():
                conversation_id = await Bx24Deal.get_chatwoot_conversation_id(
                    session, deal_id=entity_id, portal=domain
                )

        if not conversation_id:
            return {
                "messages": [],
                "conversation_id": None,
                "domain": domain,
                "deal_id": entity_id,
                "empty_reason": "Нет диалога в mbk-chat"
            }

        async with ChatwootClient() as cw:
            messages = await cw.get_all_messages(conversation_id=conversation_id)

        messages = sorted(messages or [], key=lambda m: m.get("created_at", 0))
        filter_messages = [m for m in messages if not m.get('private') and not m.get('message_type') == 2]
        return {
            "messages": filter_messages,
            "conversation_id": conversation_id,
            "domain": domain,
            "deal_id": entity_id,
            "empty_reason": None if filter_messages else "Нет сообщений в диалоге mbk-chat",
        }

    except Exception as e:
        tb = traceback.format_exc()
        await send_dev_telegram_log(f'[handle_bx24_customfield_dialog]\nОШИБКА: {tb}')
        return {
            "messages": [],
            "conversation_id": None,
            "domain": None,
            "deal_id": None,
            "empty_reason": "Ошибка при загрузке диалога."
        }


async def handle_bx24_customfield_dialog_send_contact(request: web.Request):
    """"""
    try:
        try:
            payload = await request.json()
        except Exception:
            payload = {}

        deal_id = payload.get("deal_id")
        portal_domain = payload.get("portal_domain")

        session_maker = request.app["db_sessionmaker"]
        async with session_maker() as session:
            async with session.begin():
                conversation_id = await Bx24Deal.get_chatwoot_conversation_id(session, deal_id=deal_id, portal=portal_domain)
                if not conversation_id:
                    return {"success": False, "message": "Сделка не связана с диалогом в mbk-chat!"}

        but = but_map_dict.get(portal_domain)
        deal_resp = but.call_api_method('crm.deal.get', {'id': deal_id}).get('result')
        assigned_id = deal_resp.get('ASSIGNED_BY_ID')
        user_resp = but.call_api_method('user.get', {'ID': assigned_id}).get('result', [{}])[0]
        work_phone = user_resp.get('WORK_PHONE')
        if not work_phone:
            resp = {"success": False, "message": "У ответственного не заполнен рабочий номер телефона!"}
            return web.json_response(resp, status=200)

        name = user_resp.get('NAME')
        last_name = user_resp.get('LAST_NAME')

        contact_info = build_contact_info(name, last_name, work_phone)

        async with ChatwootClient() as cw:
            if not await cw.has_client_message(conversation_id=conversation_id):
                resp = {"success": False, "message": "Не было сообщения от клиента!"}
                return web.json_response(resp, status=200)
            await cw.send_message(conversation_id=conversation_id, content=contact_info)

        await send_dev_telegram_log(f'[handle_bx24_customfield_dialog_send_contact]\nзапрос на отправку контакта\ndeal_id: {deal_id}\nportal_domain: {portal_domain}')
        resp = {"success": True,"message": "Контакт отправлен."}
        return web.json_response(resp, status=200)

    except Exception as e:
        resp = { "success": False, "message": f"Контакт не отправлен (ошибка сервера)"}
        return web.json_response(resp, status=200)
