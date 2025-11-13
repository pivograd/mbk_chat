import traceback

from aiohttp import web

from settings import INBOX_TO_TRANSPORT
from telegram.send_log import send_dev_telegram_log
from wappi.wappi_client import WappiClient


async def outbound_wappi(request, agent_code, inbox_id):
    """
    Обработчик входящих уведомлений от Chatwoot
    Транспортирует сообщения в TG через WAPPI
    """
    try:
        tg_config = INBOX_TO_TRANSPORT[inbox_id]
        wappi_instance_id, wappi_token = tg_config.get_waapi_params()
        data = await request.json()
        message = data.get("content", "")
        conversation = data.get("conversation", {})
        sender_meta = conversation.get("meta", {}).get("sender", {})
        phone = sender_meta.get("phone_number", "").lstrip("+")
        if not phone:
            return web.json_response({"status": "not phone"})

        async with WappiClient(wappi_token, wappi_instance_id) as tg_client:
            await tg_client.send_split_message(phone, message)

        return web.json_response({"status": "received"})
    except Exception as e:
        tb = traceback.format_exc()
        await send_dev_telegram_log(f'[outbound_wappi]\nНепредвиденная ошибка\n TB: {tb}', 'ERROR')
        return web.json_response({"status": "failed"})