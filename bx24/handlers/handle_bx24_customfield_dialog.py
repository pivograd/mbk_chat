import json
from urllib.parse import parse_qsl, unquote
import traceback

import aiohttp_jinja2
from aiohttp import web

from chatwoot_api.chatwoot_client import ChatwootClient
from db.models.bx_deal_cw_link import BxDealCwLink
from settings import but_map_dict, INBOX_TO_TRANSPORT
from telegram.send_log import send_dev_telegram_log
from utils.build_contact_info import build_contact_info


@aiohttp_jinja2.template("chat.html")
async def handle_bx24_customfield_dialog(request: web.Request):
    try:
        await send_dev_telegram_log(f'ХУG', 'WARNING')
        raw_qs = unquote(request.query_string or "")
        params = dict(parse_qsl(raw_qs, keep_blank_values=True))
        domain = params.get("DOMAIN")

        form = await request.post()
        placement_options = json.loads(form.get("PLACEMENT_OPTIONS", "")) or {}
        deal_id = placement_options.get("ENTITY_DATA", {}).get("entityId")

        session_maker = request.app["db_sessionmaker"]
        async with session_maker() as session:
            async with session.begin():
                links = await BxDealCwLink.get_links_for_deal(session, portal=domain, deal_id=int(deal_id))
                await send_dev_telegram_log(f'[handle_bx24_customfield_dialog]\ndeal_id: {deal_id}\nLINKS: {links}', 'WARNING')
                selected_conv_id = await BxDealCwLink.get_selected_conversation_id(session, portal=domain, deal_id=int(deal_id))

        if not links:
            await send_dev_telegram_log(f'[handle_bx24_customfield_dialog]\ndeal_id: {deal_id}\nNO LINKS: {links}', 'WARNING')
            return {
                "messages": [],
                "conversation_id": None,
                "domain": domain,
                "deal_id": deal_id,
                "links": [],
                "selected_conv_id": None,
                "empty_reason": "Сделка не связана с диалогами mbk-chat",
            }
        await send_dev_telegram_log(f'[handle_bx24_customfield_dialog]\ndeal_id: {deal_id}\nYES LINKS: {links}', 'WARNING')
        messages = []
        if selected_conv_id:
            async with ChatwootClient() as cw:
                messages = await cw.get_all_messages(conversation_id=selected_conv_id) or []

        messages = sorted(messages, key=lambda m: m.get("created_at", 0))
        filter_messages = [m for m in messages if not m.get("private") and not m.get("message_type") == 2]

        return {
            "messages": filter_messages,
            "conversation_id": selected_conv_id,
            "domain": domain,
            "deal_id": deal_id,
            "links": [
                {
                    "cw_conversation_id": l.cw_conversation_id,
                    "cw_inbox_id": l.cw_inbox_id,
                    "kind": INBOX_TO_TRANSPORT[l.cw_inbox_id].kind,
                    "is_primary": l.is_primary,
                    "created_at": int(l.created_at.timestamp()) if l.created_at else 0,
                }
                for l in links
            ],
            "selected_conv_id": selected_conv_id,
            "empty_reason": None if filter_messages else "Нет сообщений в выбранном диалоге",
        }

    except Exception:
        tb = traceback.format_exc()
        await send_dev_telegram_log(f"[handle_bx24_customfield_dialog]\nОШИБКА: {tb}")
        return {
            "messages": [],
            "conversation_id": None,
            "domain": None,
            "deal_id": None,
            "links": [],
            "selected_conv_id": None,
            "empty_reason": "Ошибка при загрузке диалога.",
        }


async def handle_bx24_customfield_select_dialog(request: web.Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    portal = payload.get("portal_domain")
    deal_id = payload.get("deal_id")
    conversation_id = payload.get("conversation_id")

    if not (portal and deal_id and conversation_id):
        return web.json_response({"success": False, "message": "Некорректные параметры"}, status=200)

    session_maker = request.app["db_sessionmaker"]
    try:
        async with session_maker() as session:
            async with session.begin():
                ok = await BxDealCwLink.set_primary_conversation(
                    session, portal=str(portal), deal_id=int(deal_id), conversation_id=int(conversation_id)
                )
                if not ok:
                    return web.json_response({"success": False, "message": "Диалог не принадлежит этой сделке"}, status=200)
        return web.json_response({"success": True, "message": "Диалог выбран"}, status=200)
    except Exception:
        tb = traceback.format_exc()
        await send_dev_telegram_log(f"[handle_bx24_customfield_select_dialog]\nОШИБКА: {tb}")
        return web.json_response({"success": False, "message": "Ошибка при выборе диалога"}, status=200)



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
                conversation_id = await BxDealCwLink.get_selected_conversation_id(
                    session, portal=portal_domain, deal_id=int(deal_id)
                )
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

        await send_dev_telegram_log(f'[handle_bx24_customfield_dialog_send_contact]\nзапрос на отправку контакта\ndeal_id: {deal_id}\nportal_domain: {portal_domain}', 'DEV')
        resp = {"success": True,"message": "Контакт отправлен."}
        return web.json_response(resp, status=200)

    except Exception as e:
        await send_dev_telegram_log(f'[handle_bx24_customfield_dialog_send_contact]\nОшибка при отправке контакта!\nerror: {e}', 'ERROR')
        resp = { "success": False, "message": f"Контакт не отправлен (ошибка сервера)"}
        return web.json_response(resp, status=200)
