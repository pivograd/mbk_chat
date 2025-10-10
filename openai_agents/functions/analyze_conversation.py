from datetime import datetime
from typing import Optional

from openai import AsyncOpenAI
from pydantic import BaseModel, Field, conlist, confloat

from chatwoot_api.chatwoot_client import ChatwootClient
from settings import OPENAI_TOKEN

def get_analyze_prompt():
    """
    Возвращает промт с акутальной датой
    """
    now_iso = datetime.now().isoformat()
    return f"""
    Ты — Аналитик клиентских диалогов
    
    Основная задача
    Определи, стоит ли отправлять прогревающее сообщение клиенту на основе анализа переписки.
    
    Принципы оценки
    
    Уважай границы клиента - если он не отвечает, возможно, не готов к общению
    Учитывай контекст завершения - как закончился последний диалог
    Оценивай временные рамки - не все паузы означают потерю интереса
    Следи за графиком серийных рассылок
    
    **График серийных рассылок
    Прогревающие сообщения отправляются 4 раза с интервалами от последнего сообщения в переписке.
    
    Первая рассылка — через 2 рабочих дня
    Вторая рассылка — через 5 рабочих дней, если была первая рассылка
    Третья рассылка — через 7 рабочих дней, если была вторая рассылка
    Четвертая рассылка — через 10 рабочих дней, если была третья рассылка
    
    Считаются только рабочие дни (пн-пт). Выходные (сб-вс) не входят в подсчет.
    Информация про ранее отправленные рассылки сохраняется в приватные сообщения. 
    
    Критерии анализа
    
    1. АНАЛИЗ ПОСЛЕДНЕГО ВЗАИМОДЕЙСТВИЯ
    
    НЕТ - если:
    Клиент явно попросил не беспокоить/перезвонить позже
    Клиент прямо отказался от услуг/сказал "не интересно"
    В диалоге была конфликтная ситуация
    Клиент жаловался на назойливость/частые сообщения
    Клиент 3 раза не ответил на прогревающие сообщения
    Клиент договорился с менеджером о звонке или встрече на определенный день и этот звонок / встреча еще не произошел
     
    ДА - если:
    Диалог завершился на позитивной ноте
    Клиент проявлял интерес, но нужно было время подумать
    Клиент просил информацию, которую тогда не предоставили
    
    2. ВРЕМЕННОЙ ФАКТОР (с учетом графика)
    НЕТ - если:
    
    Не наступил момент для очередной рассылки по графику (2, 5, 7 или 10 рабочих дней)
    Уже отправлены все 4 рассылки в серии
    
    ДА - если:
    
    Наступил момент для очередной рассылки (2, 5, 7 или 10 рабочих дней)
    Клиент ранее отвечал на прогревающие сообщения
    
    Сегодняшняя дата: {now_iso}
    """


class FollowupDecision(BaseModel):
    """Структурированный ответ модели о том, отправлять ли прогрев."""
    should_send: bool = Field(
        ...,
        description="Итоговое решение: отправлять ли прогревающее сообщение."
    )
    reasons: conlist(str, min_length=1) = Field(
        ...,
        description="Короткие причины (минимум одна)."
    )
    confidence: confloat(ge=0.0, le=1.0) = Field(
        ...,
        description="Уверенность модели от 0 до 1."
    )
    last_interaction_summary: str = Field(
        ...,
        description="Краткое резюме последнего взаимодействия."
    )
    warm_up_number: int = Field(
        ...,
        description="Номер предстоящей рассылки."
    )
    day_since_last_message: int = Field(
        ...,
        description="Прошло дней после последней рассылки."
    )
    notes: Optional[str] = Field(
        None,
        description="Доп. заметки/оговорки при нехватке данных."
    )

async def analyze_conversation(conv_id):
    """
    Анализирует диалог в Chatwoot на возможность продолжения переписки с клиентом
    """
    async with ChatwootClient() as cw:
        all_messages = await cw.get_all_messages(conv_id)

    chat_history = []
    for msg in all_messages:
        role = "user" if msg.get("message_type") == 0 else "assistant"
        content = (msg.get("content") or "").strip()
        if not content:
            continue

        # преобразуем created_at в нормальный формат
        created_at = msg.get("created_at")
        if created_at:
            dt = datetime.fromtimestamp(created_at)
            weekdays_ru = ("понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье")
            weekday = weekdays_ru[dt.weekday()]
            dt_str = f'{dt.strftime("%Y-%m-%d %H:%M:%S")} ({weekday})'
        else:
            dt_str = "unknown"

        if msg.get("private"):
            chat_history.append({
                "role": "assistant",
                "content": f"[Внутренняя заметка, не транслируй клиенту дословно!] "
                           f"(отправлено {dt_str}): {content}"})
        else:
            chat_history.append({"role": role, "content": f"(отправлено {dt_str}) {content}"})

    openai_client = AsyncOpenAI(api_key=OPENAI_TOKEN, base_url='http://150.241.122.84:3333/v1/') # в проде прокси не нужен

    resp = await openai_client.responses.parse(
        model="gpt-5-mini",
        instructions=get_analyze_prompt(),
        input=chat_history,
        text_format=FollowupDecision,
    )

    return resp.output_parsed
