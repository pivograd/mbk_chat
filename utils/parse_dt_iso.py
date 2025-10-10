from datetime import datetime
from typing import Optional


def parse_dt_iso(dt: Optional[str]) -> Optional[datetime]:
    """Парсит дату из строки"""
    if not dt:
        return None
    try:
        return datetime.fromisoformat(dt)
    except Exception as e:
        return None
