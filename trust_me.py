from aiohttp import web

from telegram.send_log import send_dev_telegram_log


async def trust_me(request: web.Request):
    await send_dev_telegram_log('[TRUSTME]', 'DEV')
    return web.Response(status=200, text=f"Йоу йоу йоу йоу, мой друг под кислотой, йоу йоу")