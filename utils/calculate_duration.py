from datetime import datetime
from typing import Optional


def calculate_duration(start: Optional[datetime], end: Optional[datetime]) -> str:
    """Высчитывает и форматирует продолжительность в человекочитабельную строку"""
    if not start or not end or end < start:
        return "0 сек."
    total = int((end - start).total_seconds())
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h: parts.append(f"{h} ч.")
    if m: parts.append(f"{m} мин.")
    if s or not parts: parts.append(f"{s} сек.")
    return " ".join(parts)
