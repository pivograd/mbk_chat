from aiohttp import web

from telegram.send_log import send_dev_telegram_log
from utils.normalize_phone import normalize_phone


async def handle_site_comeback(request):
    """
    Обработчик заявок с сайта LEADON
    """
    data = await request.json()
    try:
        phone = normalize_phone(data.get("phone", ''))
        domain = data.get("domain")
        if not domain or not phone:
            return web.Response(text="❌ Не указан телефон или домен", status=400)

        await send_dev_telegram_log(f'[handle_site_comeback]\ndata: {data}', 'DEV')
        return web.Response(text="Повторное посещение зафиксированно!", status=200)
    except Exception as e:
        await send_dev_telegram_log(f'[handle_site_comeback]\nКритическая ошибка\nDATA: {data}\nERROR: {e}',
                                    'ERROR')
        return web.Response(text='Серверная ошибка', status=500)
