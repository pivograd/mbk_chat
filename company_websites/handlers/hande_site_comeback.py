from aiohttp import web

from chatwoot_api.chatwoot_client import ChatwootClient
from telegram.send_log import send_dev_telegram_log
from utils.normalize_phone import normalize_phone
from chatwoot_api.functions.safe_send_to_chatwoot import safe_send_to_chatwoot

async def handle_site_comeback(request):
    """
    Обработчик заявок с сайта LEADON
    """
    data = await request.json()
    try:
        phone = normalize_phone(data.get("phone", '')).lstrip('+')
        domain = data.get("domain")
        if not domain or not phone:
            return web.Response(text="❌ Не указан телефон или домен", status=400)
        async with ChatwootClient() as cw:
            contact_id = await cw.get_contact_id(phone)
            conversations = await cw.get_conversations(contact_id)
            for conversation in conversations:
                await cw.send_message(conversation['id'], f'Клиент посетил наш сайт: {domain}', private=True)
        await send_dev_telegram_log(f'[handle_site_comeback]\ndata: {data}', 'DEV')
        return web.Response(text="Повторное посещение зафиксированно!", status=200)
    except Exception as e:
        await send_dev_telegram_log(f'[handle_site_comeback]\nКритическая ошибка\nDATA: {data}\nERROR: {e}',
                                    'ERROR')
        return web.Response(text='Серверная ошибка', status=500)
