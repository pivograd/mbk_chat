from datetime import datetime

from chatwoot_api.chatwoot_client import ChatwootClient
from settings import OPENAI_TOKEN
from telegram.send_log import send_dev_telegram_log
from utils.normalize_phone import normalize_phone

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
Проанализировать контекст предыдущих сообщений с этим клиентом. Если предыдущие сообщения повторяют один и тот же запрос, не дублируй его дословно, а придумывай новый вопрос, который:
должен быть уникальным,
связан с новым запросом клиента,
опирается на информацию из предыдущих сообщений,
уточняет или расширяет запрос клиента.

ФОРМАТ ОТВЕТА (СТРОГО)
Ты всегда отвечаешь одним коротким сообщением по шаблону:
Правильно понимаю, что хотели бы {короткое описание того, что человек запросил}?
Где {короткое описание того, что человек запросил} — это твоя сжатая формулировка смысла заявки на основе title и comment и анализа предыдущих сообщений.


ЖЁСТКИЕ ОГРАНИЧЕНИЯ
Не добавляй никаких других вопросов, кроме фразы «Правильно понимаю, что хотели бы …?».
В случае повторной отправки любой формы на сайте от клиента не начинай вопрос с «Правильно понимаю, что хотели бы …?». 
Переформулируй и сделай его уникальным, сославшись на предыдущее сообщение.  Например, "Видел, что вы оставили еще заявку", "Замечаю, что пришла новая заявка — правильно ли я понимаю, что хотите подборку одноэтажных домов с 3 спальнями?", "Получил вашу новую заявку — хотели бы записаться на экскурсию по строительству?", "Замечаю ещё один ваш запрос — уточните, интересует ли консультация по будущему дому?" и так далее.

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

async def get_message_from_ai(lead_data: Dict[str, Any], inbox_id: int) -> str:
    """
    Возвращает одно уточняющее сообщение для клиента по заявке.
    """
    user_payload = _build_user_payload(lead_data)

    identifier = normalize_phone(lead_data.get("phone", '')).lstrip('+')

    async with ChatwootClient() as cw:
        contact_id = await cw.get_contact_id(identifier)
        if contact_id:
            conversation_id = await cw.get_conversation_id(contact_id, inbox_id)
            messages = await cw.get_all_messages(conversation_id)

    history = []


    if messages:
        for msg in messages:
            role = "user" if msg.get("message_type") == 0 else "assistant"
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            created_at = msg.get("created_at")
            if created_at:
                dt_str = datetime.fromtimestamp(created_at).strftime("%Y-%m-%d %H:%M:%S")
            else:
                dt_str = "unknown"

            if msg.get("private"):
                history.append({
                    "role": "assistant",
                    "content": f"[Внутренняя заметка, не транслируй клиенту дословно!] "
                               f"(отправлено {dt_str}): {content}"})
            elif msg.get("message_type") == 2:
                history.append({
                    "role": "assistant",
                    "content": f"[СИСТЕМНАЯ ИНФОРМАЦИЯ!]"
                               f"{content}"})
            else:
                history.append({"role": role, "content": f"(отправлено {dt_str}) {content}"})

    history.append({"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)})
    try:
        openai_client = AsyncOpenAI(api_key=OPENAI_TOKEN)
        resp = await openai_client.responses.parse(
            model="gpt-5",
            instructions=prompt,
            input=history,
        )
        return resp.output_text

    except Exception as e:

        await send_dev_telegram_log(f'[get_message_from_ai]\nКритическая ошибка!\nERROR: {e}')
        return "Добрый день! Подскажите, какой расчёт/подборку проектов вы хотели получить?"

