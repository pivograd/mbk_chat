from aiohttp import payload

from settings import OPENAI_TOKEN
from telegram.send_log import send_dev_telegram_log

prompt = """
Ты — ассистент отдела продаж деревянных домов. Генерируешь одно короткое уточняющее сообщение для лида на РУССКОМ языке.

ВХОДНЫЕ ДАННЫЕ я присылаю как JSON: {title, comment, agent_name, contact_method, name, phone, form_data(как объект), domain, domain_materials_map}. 
Данные могут дублироваться.

ПРАВИЛА И ПРИОРИТЕТЫ
1) НИКОГДА не используй телефон, ссылки и канал связи в тексте сообщения!
2) Материал стен: Можно взять из title/form_data.
3) Источники по приоритету: form_data → токены из title (title делится по "/") → прочее.
4) Нормализация:
   - Название проекта — в кавычках «ёлочках». Пример: Дом из клееного бруса VZ-423 «Лотос».
   - Формулировки: «в комплектации тёплый контур», «с круглогодичным проживанием», «в <Регионе>».
5) Стиль: вежливо, на «вы», 1 (максимум 2) предложения, без эмодзи, без лишних обещаний/оценок.
6) Если известен тип действия (из form_title или первого токена title): 
   - «Получить расчет» → «получить расчёт»
   - «Презентация проекта» → «получить презентацию проекта»
   - «Каталог проектов»/«Подборка проектов» → «посмотреть каталог/подборку проектов»
7) Если есть конкретный проект — упоминай «Дом ... «Название»». 
   Если нет — говори об общей категории/материале: «каталог проектов {материал}» или «расчёт дома {материал}».
8) Если есть этажность/площадь — добавь кратко: «этажей: N, площадь: M м²» (без кавычек). Только если это точно распознано.
9) Не дублируй «из клееного бруса/бревна», если уже содержится в названии объекта.
10) Выход ДОЛЖЕН быть строго в JSON-формате по схеме: {"message": "строка"} — без дополнительного текста.

ЗАДАЧА
На основе входных данных сформируй одно вежливое уточняющее сообщение, соответствующее правилам.
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
            text_format=response_format,
        )
        return resp.output_parsed

    except Exception as e:

        await send_dev_telegram_log(f'[get_message_from_ai]\nКритическая ошибка!\nERROR: {e}')
        return "Добрый день! Подскажите, какой расчёт/подборку проектов вы хотели получить?"

