from aiohttp import web

from green_api.send_to_greenapi import send_to_greenapi


async def outbound_green_api(request, agent_code, inbox_id):
    """
    Обработчик входящих уведомлений от Chatwoot
    Транспортирует сообщения в WhatsApp через GREEN API
    """
    data = await request.json()
    message = data.get("content", "")
    attachments = data.get("attachments", [])
    conversation = data.get("conversation", {})
    sender_meta = conversation.get("meta", {}).get("sender", {})
    phone = sender_meta.get("phone_number", "").lstrip("+")
    if not phone:
        return web.json_response({"status": "not phone"})

    send_to_greenapi(agent_code, phone, message, attachments)

    return web.json_response({"status": "received"})