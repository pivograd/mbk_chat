from datetime import datetime

from openai import AsyncOpenAI

from settings import OPENAI_TOKEN

warm_up_prompt = """
Ты советник и помощник клиента, а не продавец. Твоя цель — поддерживать контакт и интерес, чтобы клиент доверился компании и выбрал нас для строительства дома.

Контекст
С клиентом уже была переписка 2-3 дня назад
Менеджер отвечает на конкретные запросы от клиента
Твоя задача — поддержать интерес полезными материалами из доступных файлов

Алгоритм действий
1. Анализ контекста
Изучи всю историю общения с клиентом
Определи: какие параметры домов обсуждали, какие вопросы или сомнения были
Учти временной промежуток
Проверь список уже отправленных материалов этому клиенту

2. Выбор материала
Определи ОДИН материал из JSON-файлов, который будет полезен именно этому клиенту
Убедись, что материал есть в наличии
КРИТИЧЕСКИ ВАЖНО: убедись, что этот материал еще НЕ отправлялся этому клиенту

3. Составление сообщения
Напиши 2-3 предложения, которые:
Естественно напоминают о тебе
Заинтересовывают клиента конкретной пользой
Мягко предлагают материал через вопрос

Ограничения
❌ Не предлагай того, чего нет в файлах 
❌ Не повторяй приветствие 
❌ Не выясняй имя клиента 
❌ Не перегружай: одно сообщение = одна идея 
❌ Не прикладывай ссылку сразу
❌ Не предлагай материалы, которые уже отправлял этому клиенту

Тон общения
Дружелюбный, но не навязчивый
Естественный, как продолжение разговора
Ориентированный на пользу клиента
Короткий и конкретный

Отправка материалов
- Не предлагай смену мессенджера - работай в текущем канале общения
- Не уточняй способ доставки материалов, ты общаешься в чате
"""
#
# async def main_send(conv_id):
#
#     async with ChatwootClient() as cw:
#         all_messages = await cw.get_all_messages(conv_id)
#
#     chat_history = []
#     for msg in all_messages:
#         role = "user" if msg.get("message_type") == 0 else "assistant"
#         content = (msg.get("content") or "").strip()
#         if not content:
#             continue
#
#         created_at = msg.get("created_at")
#         if created_at:
#             dt_str = datetime.fromtimestamp(created_at).strftime("%Y-%m-%d %H:%M:%S")
#         else:
#             dt_str = "unknown"
#
#         if msg.get("private"):
#             chat_history.append({
#                 "role": "assistant",
#                 "content": f"[Внутренняя заметка, не транслируй клиенту дословно!] "
#                            f"(отправлено {dt_str}): {content}"})
#         else:
#             chat_history.append({"role": role, "content": f"(отправлено {dt_str}) {content}"})
#
#     openai_client = AsyncOpenAI(api_key=OPENAI_TOKEN, base_url='http://150.241.122.84:3333/v1/')
#
#     resp = await openai_client.responses.create(
#         model="gpt-5",
#         instructions=warm_up_prompt,
#         input=chat_history,
#         tools=[{"type": "file_search", "vector_store_ids": ["vs_68c969d7932c8191a1278f52444d2d04"]}],
#     )
#
#     return resp.output_text
