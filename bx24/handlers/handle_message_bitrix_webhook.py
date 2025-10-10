import re
from urllib.parse import unquote

from aiohttp import web

from chatwoot_api.functions.safe_send_to_chatwoot import safe_send_to_chatwoot
from settings import AGENTS_BY_CODE
from telegram.send_log import send_dev_telegram_log
from utils.normalize_phone import normalize_phone


async def handle_message_bitrix_webhook(request):
    """
    Обработчик для отправки сообщения контакту из сделки BX24
    """
    try:
        query_string = unquote(request.query_string)
        parts = query_string.split("&")
        params = {}

        for item in parts:
            key, value = item.split("=", 1)
            params[key.strip()] = value.strip()

        await send_dev_telegram_log(f'[handle_message_bitrix_webhook]\nparams: {params}')

        # Инициализируем переменные
        name = params.get('name', 'Без имени')
        phone = params.get('phone', '')
        comment = params.get('comment', '')
        message = params.get('message', 'Здравствуйте!')
        channel = params.get('channel')
        wa_cfg = AGENTS_BY_CODE[channel].get_wa_cfg()
        if not wa_cfg:
            await send_dev_telegram_log(f'[handle_message_bitrix_webhook]\nНе удалось получить WAConfig для Агента: {channel}', 'WARNING')
            return web.Response(text="❌ Не указан агент", status=400)

        # убираем BB код из текста
        comment = re.sub(r'\[/?\w+\]', '', comment).strip('_')

        phone = normalize_phone(phone)
        if not phone:
            return web.Response(text="❌ Неверный номер телефона", status=400)

        await safe_send_to_chatwoot(phone, name, message, wa_cfg.chatwoot, comment=comment)
        return web.Response(text="✅ Контакт обработан")

    except Exception as e:
        # TODO log
        return web.Response(text="❌ Ошибка обработки", status=500)
