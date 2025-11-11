from aiohttp import web

from chatwoot_api.functions.safe_send_to_chatwoot import safe_send_to_chatwoot
from settings import AGENTS_BY_CODE
from telegram.send_log import send_dev_telegram_log
from utils.normalize_phone import normalize_phone


async def handle_lead_on_site(request):
    """
    Обработчик заявок с сайта LEADON
    """
    data = await request.json()
    try:
        await send_dev_telegram_log(f'[handle_lead_on_site]\nЗаявка с LEADON', 'DEV')
        agent_name = data.get("agent_name")
        phone = normalize_phone(data.get("phone", ''))
        if not agent_name or not phone:
            return web.Response(text="❌ Недостаточно данных!", status=400)

        message = 'Здраствуйте, правильно понимаю, что хотели бы получить каталог проектов?'
        kind = 'wa'
        agent_cfg = AGENTS_BY_CODE[agent_name]
        session_maker = request.app["db_sessionmaker"]
        async with session_maker() as session:
            transport_cfg = await agent_cfg.pick_transport(session, kind, phone)
        if not transport_cfg:
            await send_dev_telegram_log(
                f'[handle_lead_on_site]\nNO VALID TRANSPORT\nkind: {kind}\n phone: {phone}\nagent_cfg: {agent_cfg}', 'WARNING')
            return web.json_response({"status": "error", "message": "no valid transport"})
        name = f'LEADON {phone}'
        await safe_send_to_chatwoot(phone, name, message, transport_cfg.chatwoot)
        return web.json_response({"status": "ok"})

    except Exception as e:
        await send_dev_telegram_log(f'[handle_lead_on_site]\nКРИТИЧЕСКАЯ ОШИБКА ПРИ ОБРАБОТКЕ ЗАПРОСА!!\nERROR: {e}', 'ERROR')
        return web.Response(text="❌ Ошибка на сервере!", status=500)
