from aiohttp import web

from settings import INBOX_TO_TRANSPORT
from green_api.send_contact import send_contact
from green_api.send_text import send_text_message
from telegram.send_log import send_dev_telegram_log
from utils.parse_contact_payload import parse_contact_message


async def send_manager_contact_card(data, kind, inbox_id):
    """
    Функция для отправки контакта менеджера клиенту в нужный источник
    """
    message = data.get("content", "")
    name, last_name, contact_phone = parse_contact_message(message)

    conversation = data.get("conversation", {})

    sender_meta = conversation.get("meta", {}).get("sender", {})
    client_phone = sender_meta.get("phone_number", "").lstrip("+")

    transport_cfg = INBOX_TO_TRANSPORT.get(inbox_id)
    manager_info = f'Ваш менеджер по строительству {last_name} {name}.\nТелефон: {contact_phone}'
    if kind == 'wa':
        await send_text_message(manager_info, client_phone, wa_config=transport_cfg)
        await send_contact(name, last_name, contact_phone, client_phone, wa_config=transport_cfg)
        return web.json_response({"status": "received"})
    elif kind == 'tg':
        tg_client = transport_cfg.get_wappi_client()
        await tg_client.send_message(client_phone, manager_info)
        await tg_client.send_contact(client_phone, contact_phone, f'{last_name} {name}')
        return web.json_response({"status": "received"})
    await send_dev_telegram_log(f'[send_manager_contact_card]\nНе удалость отправить контакт менеджера!\nconfig: {transport_cfg}', 'WARNING')
    return web.json_response({"status": "received"})
