from typing import Optional

from openai import AsyncOpenAI

from settings import OPENAI_TOKEN, MODEL_MAIN

# Твой системный промпт (оставил как есть)
image_prompt = """
Ты — эксперт по зрительному пониманию. Твоя задача — генерировать точные и лаконичные русскоязычные описания изображений из входных данных. 
Правила:
- Не выдумывай фактов, которых нельзя надёжно увидеть.
- Если не уверен, используй «возможно»/«неопределимо».
- Не делай чувствительных предположений (раса, национальность, возраст, здоровье, беременность и т.п.), если это не явно и недвусмысленно видно.
- Если на изображении есть текст — извлеки его без интерпретаций.
- Будь конкретен: количества, относительные позиции, ключевые цвета, тип освещения, ракурс.
- Пиши по-русски, просто и естественно.
""".strip()

async def analyze_image(
    image_url: Optional[str] = None,
    base64_image: Optional[str] = None,
    model: str = MODEL_MAIN) -> str:
    """
    Анализирует изображение и возвращает русскоязычное описание.
    Можно передать либо публичный image_url, либо локальный image_path.
    """
    client = AsyncOpenAI(api_key=OPENAI_TOKEN) # , base_url='http://150.241.122.84:3333/v1/'
    content_items =[]
    image = image_url
    if base64_image:
        image = f"data:image/jpeg;base64,{base64_image}"
    content_items.append({"type": "input_image", "image_url": image})

    resp = await client.responses.create(
        model=model,
        instructions=image_prompt,
        input=[{"role": "user", "content": content_items}]
    )

    return resp.output_text
