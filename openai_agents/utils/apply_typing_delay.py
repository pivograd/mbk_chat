import re
import asyncio

from telegram.send_log import send_dev_telegram_log
from utils.split_message_by_links import split_message_by_links, FILE_LINK_REGEX


def strip_links_for_counting(text: str) -> str:
    """Возвращает текст без ссылок (URL и автоссылок),
    при этом у Markdown-ссылок оставляет только якорный текст."""
    cleaned_parts = []
    for part in split_message_by_links(text):
        txt = part.lstrip(".,!? \t;:-").strip()
        if len(txt) < 2:
            continue
        if re.match(FILE_LINK_REGEX, txt, re.IGNORECASE):
            continue
        else:
            cleaned_parts.append(txt)

    return ' '.join(cleaned_parts)

def visible_char_count(text: str) -> int:
    """Подсчитывает видимые символы без ссылок."""
    cleaned = strip_links_for_counting(text or "")
    return len(cleaned)

async def apply_typing_delay(
    reply: str,
    thinking_seconds: float,
    rate_chars_per_min: float = 200.0,
    hard_cap_seconds: float = 180.0
) -> float:
    """
    Делает искусственную задержку, чтобы агент "отвечал"
    с заданной скоростью (по символам в минуту),
    игнорируя ссылки в тексте.
    """
    char_count = visible_char_count(reply)

    if rate_chars_per_min <= 0:
        rate_chars_per_min = 200.0
    if thinking_seconds < 0:
        thinking_seconds = 0.0

    target_seconds = (char_count / rate_chars_per_min) * 60.0
    raw_delay = target_seconds - thinking_seconds

    if raw_delay > 0:
        if raw_delay > hard_cap_seconds:
            raw_delay = hard_cap_seconds
        await send_dev_telegram_log(f'[apply_typing_delay]\nЗапускаем сон на {raw_delay:.2f} секунд', 'DEV')
        await asyncio.sleep(raw_delay)
        await send_dev_telegram_log(f'[apply_typing_delay]\nЗакончили сон на {raw_delay:.2f} секунд', 'DEV')

    return raw_delay
