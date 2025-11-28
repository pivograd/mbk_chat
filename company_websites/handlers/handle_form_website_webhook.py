import json
import re

from aiohttp import web

from chatwoot_api.functions.safe_send_to_chatwoot import safe_send_to_chatwoot
from settings import AGENTS_BY_CODE
from telegram.send_log import send_dev_telegram_log
from utils.get_message_from_ai import get_message_from_ai
from utils.get_message_from_comment import get_message_from_comment
from utils.normalize_phone import normalize_phone


async def handle_form_website_webhook(request):
    """
    Обработчик заполнения какой либо формы на сайте
    """
    data = await request.json()
    try:
        agent_name = data.get("agent_name")
        await send_dev_telegram_log(f'NEW\n[handle_form_website_webhook]\nЗапрос с лендоса!\n\ndata: {data}', 'DEV')
        if not agent_name:
            await send_dev_telegram_log(f'[handle_form_website_webhook]\nНе указано имя агента!\ndata: {data}', 'WARNING')
            return web.Response(text="❌ Не указано имя агента", status=400)

        if data.get('title') == 'Пусть назывется сделка Смета конкурентов':
            return web.Response(text="На эту форму не реагируем", status=200)

        phone = re.sub(r'\D', '', data.get("phone", ""))
        domain = data.get("title", "").split(' - ')[-1]
        phone = normalize_phone(phone)
        comment = data.get("comment", "")
        name_match = re.search(r'Имя\s*:\s*(.+)', comment)
        match = re.search(r'Форма\s*:\s*([^\n\r]+)', comment)
        form_type = match.group(1).strip() if match else 'quiz'
        message = get_message_from_comment(comment, form_type, domain)
        form_data = data.get("form_data")
        if form_data:
            form_data_json = json.loads(form_data)
            if form_data_json.get('form_quiz_construction_region') == "Московская область":
                agent_name = 'pavel'

        name = None
        if name_match:
            name = name_match.group(1).strip()
        if not name:
            name = data.get("name")
        if not name:
            name = f"Заявка с сайта! {phone}"

        contact_method = data.get("contact_method", 'WhatsApp')
        kind = 'tg' if contact_method.lower() == 'telegram' else 'wa'
        agent_cfg = AGENTS_BY_CODE[agent_name]

        session_maker = request.app["db_sessionmaker"]
        async with session_maker() as session:
            transport_cfg = await agent_cfg.pick_transport(session, kind, phone)

        if not transport_cfg:
            await send_dev_telegram_log(f'[handle_form_website_webhook]\nkind: {kind}\n phone: {phone}\nagent_cfg: {agent_cfg}', 'WARNING')
            return web.json_response({"status": "error", "message": "no valid transport"})

        if kind == 'tg':
            async with transport_cfg.get_wappi_client() as wappi_client:
                # Сохраняем номер телефона в контакты ТГ
                await wappi_client.get_or_create_contact(phone, name)

        if form_data:
            inbox_id = transport_cfg.chatwoot.inbox.inbox_id

            message = await get_message_from_ai(data, inbox_id)
            await send_dev_telegram_log(f'[handle_form_website_webhook]\nmessage: {message}', 'DEV')

        await safe_send_to_chatwoot(phone, name, message, transport_cfg.chatwoot, comment=comment)
        return web.Response(text="Отправили сообщение", status=200)

    except Exception as e:
        await send_dev_telegram_log(f'[handle_form_website_webhook]\nКритическая ошибка\nDATA: {data}\nERROR: {e}', 'ERROR')
        return web.Response(text='Серверная ошибка', status=500)
