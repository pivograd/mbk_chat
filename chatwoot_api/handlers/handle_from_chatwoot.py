from aiohttp import web

from chatwoot_api.functions.send_agent_contact import send_agent_contact_card
from chatwoot_api.functions.send_manager_contact import send_manager_contact_card
from green_api.handlers.outbound_green_api import outbound_green_api
from wappi.handlers.outbound_wappi import outbound_wappi


async def handle_from_chatwoot(request, agent_code, kind, inbox_id):
    """
    Обрабатывает исходящие сообщения из Chatwoot
    """
    data = await request.json()
    event_type = data.get("event")

    if data.get("private", False):
        return web.json_response({"status": "skipped: private message"})

    if event_type != "message_created":
        return web.json_response({"status": "ignored"})

    if data.get("message_type") != "outgoing":
        return web.json_response({"status": "ignored not outgoing"})
    message = data.get("content", "")

    if message.startswith("[Менеджер по строительству]"):
        await send_manager_contact_card(data, kind, inbox_id)
        return web.json_response({"status": "ok"})
    elif message.startswith("[Мой контакт]"):
        await send_agent_contact_card(data, kind, inbox_id)
        return web.json_response({"status": "ok"})

    if kind == "wa":
        return await outbound_green_api(request, agent_code, inbox_id)
    elif kind == "tg":
        return await outbound_wappi(request, agent_code, inbox_id)

    return web.Response(status=404, text=f"Unsupported kind: {kind}")
