from aiohttp import payload

from settings import OPENAI_TOKEN
from telegram.send_log import send_dev_telegram_log

prompt = """
Ты — менеджер в компании «Вологодское Зодчество». Ты пишешь первое сообщение клиенту в WhatsApp после отправки любой формы на сайте.

ТВОЯ ЗАДАЧА
Проанализировать поля title и comment.
Понять, что именно хотел получить клиент:
подборку проектов,
расчёт / смету,
смету в ипотеку,
презентацию проекта,
индивидуальный проект,
экскурсию / просмотр домов,
обратный звонок,
консультацию и т.п.
Сформулировать короткое и понятное описание запроса в одну фразу в форме: «получить подборку одноэтажных домов 240–380 м² с 3 спальнями», «получить расчёт по дому VZ-789 „Порту“», «получить смету для ипотеки по дому …», «получить презентацию проекта …», «заказать индивидуальный проект дома», «записаться на экскурсию на строительство» и т.д.
Если данных мало или структура title непонятна — делай описание более общим: «получить консультацию по строительству дома», «получить расчёт по будущему дому», «обсудить проект дома» и т.п.

ФОРМАТ ОТВЕТА (СТРОГО)
Ты всегда отвечаешь одним коротким сообщением по шаблону:
Правильно понимаю, что хотели бы {короткое описание того, что человек запросил}?
Где {короткое описание того, что человек запросил} — это твоя сжатая формулировка смысла заявки на основе title и comment.

ЖЁСТКИЕ ОГРАНИЧЕНИЯ
Не добавляй никаких других вопросов, кроме фразы «Правильно понимаю, что хотели бы …?».
Не дописывай благодарности, смайлики, лишние фразы («спасибо за обращение», «готов вам помочь» и т.п.).
Не используй маркдауны, кавычки вокруг всего сообщения, JSON, пояснения к ответу.
На выходе ты возвращаешь только текст сообщения для клиента, полностью готовый к отправке в WhatsApp, строго по указанному шаблону.
"""

test_data = {
  "title": "Получить расчет/Дом из клееного бруса VZ-423 «Лотос»/Тёплый контур/Круглогодичное/Вологодская область/Безнал/WhatsApp",
  "comment": "https://xn--b1aaceafbozh6abbccd6bht1h.xn--p1ai/doma-iz-brusa/kleenyy/vz-423/",
  "agent_name": "maksim",
  "contact_method": "WhatsApp",
  "name": "Егор",
  "phone": "+79811454737",
  "form_data": {
    "form_title":"Получить расчет",
    "form_quiz_select_configuration":"Тёплый контур",
    "form_quiz_seasonality_of_accommodation":"Круглогодичное",
    "form_quiz_construction_region":"Вологодская область",
    "form_quiz_type_of_financing":"Безнал",
    "contact_method":"WhatsApp",
    "form_project": None,
  },
}


from typing import Any, Dict
import json
from openai import AsyncOpenAI

def _build_user_payload(lead) -> Dict[str, Any]:
    form_data = lead.get("form_data")
    if isinstance(form_data, str):
        try:
            form_data = json.loads(form_data)
        except Exception:
            form_data = {}
    elif not isinstance(form_data, dict):
        form_data = {}

    return {
        "title": lead.get("title"),
        "comment": lead.get("comment"),
        "agent_name": lead.get("agent_name"),
        "contact_method": lead.get("contact_method"),
        "name": lead.get("name"),
        "phone": lead.get("phone"),
        "form_data": form_data,
    }

async def get_message_from_ai(lead_data: Dict[str, Any]) -> str:
    """
    Возвращает одно уточняющее сообщение для клиента по заявке.
    """
    user_payload = _build_user_payload(lead_data)

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "lead_message",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Короткое вежливое уточняющее сообщение на русском языке."
                    }
                },
                "required": ["message"]
            }
        }
    }

    messages = [
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]

    try:
        openai_client = AsyncOpenAI(api_key=OPENAI_TOKEN)
        resp = await openai_client.responses.parse(
            model="gpt-5",
            instructions=prompt,
            input=messages,
        )
        return resp.output_text

    except Exception as e:

        await send_dev_telegram_log(f'[get_message_from_ai]\nКритическая ошибка!\nERROR: {e}')
        return "Добрый день! Подскажите, какой расчёт/подборку проектов вы хотели получить?"

