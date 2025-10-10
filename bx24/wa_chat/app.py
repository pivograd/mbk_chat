import base64
import json
from datetime import datetime
import os
from io import BytesIO

import mammoth
from dotenv import load_dotenv
import requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from bx24.bx_utils.bitrix_token import BitrixToken
from settings import AGENTS

app = FastAPI()
templates = Jinja2Templates(directory="templates")


load_dotenv()

GREEN_API_URL = os.getenv('GREEN_API_URL')
DOMAIN = os.getenv('DOMAIN')

def get_chat_history(phone: str, agent_key: str):
    agent = AGENTS.get(agent_key)
    if not agent:
        raise ValueError("Агент не найден")
    url = f"https://{GREEN_API_URL}/waInstance{agent['ID_INSTANCE']}/getChatHistory/{agent['GREEN_API_TOKEN']}"
    payload = {"chatId": f"{phone}@c.us", "count": 300}
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error in get_chat_history: {e}")
        return []


def format_timestamp(ts):
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

def decode_placement_options(placement_options_b64: str):
    try:
        decoded = base64.b64decode(placement_options_b64)
        data = json.loads(decoded)
        return data
    except Exception as e:
        # TODO: лог
        print(f"Error decoding placement_options: {e}")
        return {}

def docx_to_html(docx_bytes: bytes) -> tuple[str, list]:
    """
    Конвертация .docx -> HTML. Картинки инлайн в base64.
    Возвращаем html и сообщения mammoth (warnings).
    """
    with BytesIO(docx_bytes) as bio:
        result = mammoth.convert_to_html(bio)
        html = result.value
        messages = result.messages
        return html, messages

@app.api_route("/vz/chat", methods=["GET", "POST"], response_class=HTMLResponse)
async def chat(request: Request):
    try:
        form = await request.form()
        agent_key = form.get("agent", next(iter(AGENTS)))
        placement_options = form.get("PLACEMENT_OPTIONS", '')
        placement_params = json.loads(placement_options)

        deal_id = placement_params.get("ID")
        token = form.get("AUTH_ID")
        but = BitrixToken(domain=DOMAIN, auth_token=token)
        result = but.call_api_method('crm.deal.contact.items.get', {'id': deal_id})['result'][0]
        contact_id = result["CONTACT_ID"]
        phone = but.call_api_method('crm.contact.get', {'id': contact_id})['result'].get('PHONE')[0].get('VALUE')
        if not phone:
            return HTMLResponse("<b>Не найден номер телефона в placement_options</b>", status_code=400)

        if phone.startswith("8"):
            phone = "7" + phone[1:]
        elif phone.startswith("+"):
            phone = phone[1:]

        messages = get_chat_history(phone, agent_key)

        # Сортируем и форматируем дату
        for m in messages:
            ts = m.get("timestamp")
            m["dt"] = format_timestamp(ts) if ts else ""

        return templates.TemplateResponse("chat.html", {
            "request": request,
            "messages": messages[::-1],
            "phone": phone,
            "dialog_error": False,
            "selected_agent": agent_key,
            "placement_options": placement_options,
            "auth_id": token,
            "agents": list(AGENTS.keys()),
        })

    except Exception as e:
        # TODO: лог
        return templates.TemplateResponse("chat.html", {
            "request": request,
            "dialog_error": True,
            "messages": [],
            "phone": "",
            "selected_agent": "",
            "agents": list(AGENTS.keys()),
        })
@app.api_route("/vz/payment_schedule", methods=["GET", "POST"], response_class=HTMLResponse)
async def payment_schedule(request: Request):
    try:
        form = await request.form()
        placement_options = form.get("PLACEMENT_OPTIONS", '')
        placement_params = json.loads(placement_options or "{}")

        deal_id = placement_params.get("ID")
        if not deal_id:
            return templates.TemplateResponse("schedule.html", {
                "request": request,
                "error": "Не передан ID сделки",
                "schedule_html": "",
                "deal_id": None,
            })

        token = form.get("AUTH_ID")
        if not token:
            return templates.TemplateResponse("schedule.html", {
                "request": request,
                "error": "Не передан AUTH_ID (токен)",
                "schedule_html": "",
                "deal_id": deal_id,
            })

        but = BitrixToken(domain=DOMAIN, auth_token=token)
        resp = but.call_api_method('crm.deal.get', {'id': deal_id})

        SCHEDULE_FILE_FIELD = 'UF_CRM_1547709653'
        file_info = resp.get('result', {}).get(SCHEDULE_FILE_FIELD)
        if not file_info:
            return templates.TemplateResponse("schedule.html", {
                "request": request,
                "error": "В сделке не найден файл графика платежей",
                "schedule_html": "",
                "deal_id": deal_id,
            })

        file_url = file_info.get('downloadUrl')
        if not file_url:
            return templates.TemplateResponse("schedule.html", {
                "request": request,
                "error": "Для файла нет downloadUrl",
                "schedule_html": "",
                "deal_id": deal_id,
            })

        # downloadUrl в ответе Bitrix обычно относительный — добавим домен
        if file_url.startswith("/"):
            download_url = f"https://{DOMAIN}{file_url}"
        else:
            download_url = file_url

        resp = requests.get(download_url, timeout=30)
        resp.raise_for_status()

        docx_bytes = resp.content

        schedule_html, mammoth_messages = docx_to_html(docx_bytes)


        return templates.TemplateResponse("schedule.html", {
            "request": request,
            "error": "",
            "schedule_html": schedule_html,
            "deal_id": deal_id,
            "mammoth_messages": mammoth_messages,  # можно вывести в dev-режиме
        })

    except Exception as e:
        # TODO: логирование e
        return templates.TemplateResponse("schedule.html", {
            "request": request,
            "error": f"Ошибка при загрузке/рендеринге файла",
            "schedule_html": "",
            "deal_id": None,
        })


# встройка resp = but.call_api_method('placement.bind', {'PLACEMENT': 'CRM_DEAL_DETAIL_TAB', 'HANDLER': handler, 'TITLE': 'DEV WA CHAT'})
# handler = 'https://2ff956f5-6f43-4233-89d5-d9eaa6db756f.tunnel4.com'
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=999)
