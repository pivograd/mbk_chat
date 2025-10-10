import traceback

from aiohttp import web

from settings import INBOX_TO_TRANSPORT
from green_api.functions.get_instance_settings import get_instance_phone
from green_api.send_contact import green_api_send_agent_contact
from green_api.send_text import send_text_message
from telegram.send_log import send_dev_telegram_log


async def send_agent_contact_card(data):
    """
    Функция для отправки контакта агента клиенту в нужный источник
    """
    try:
        conversation = data.get("conversation", {})
        inbox_id = conversation.get("inbox_id")

        sender_meta = conversation.get("meta", {}).get("sender", {})
        client_phone = sender_meta.get("phone_number", "").lstrip("+")

        transport_cfg = INBOX_TO_TRANSPORT.get(inbox_id)

        msg = 'Сохраните мой контакт — вернемся к разговору, когда будете готовы'

        if transport_cfg.kind == 'wa':
            agent_phone = await get_instance_phone(transport_cfg)
            await send_text_message(msg, client_phone, wa_config=transport_cfg)
            await green_api_send_agent_contact(transport_cfg, agent_phone, client_phone)
            return web.json_response({"status": "received"})
        elif transport_cfg.kind == 'tg':
            tg_client = transport_cfg.get_wappi_client()
            agent_phone = await tg_client.get_instance_phone()
            await tg_client.send_message(client_phone, msg)
            await tg_client.send_contact(client_phone, agent_phone)
            return web.json_response({"status": "received"})

        await send_dev_telegram_log(f'[send_agent_contact_card]\nНе удалость отправить контакт агента!\nconfig: {transport_cfg}', 'WARNING')
        return web.Response(status=404, text=f"Unsupported kind: {transport_cfg.kind}")
    except Exception as e:
        tb = traceback.format_exc()
        await send_dev_telegram_log(f'[send_agent_contact_card]\nКритическая ошибка!\nError: {tb}', 'ERROR')
        return web.Response(status=404)