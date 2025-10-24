from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Any

from utils.calculate_duration import calculate_duration
from utils.parse_dt_iso import parse_dt_iso


@dataclass
class CallInfo:
    id: str
    subject: Optional[str]
    direction: str
    start: Optional[datetime]
    end: Optional[datetime]
    duration_human: str
    status: str
    file_id: Optional[str]


def _extract_transcription_text(val: Any) -> str | None:
    """
    """
    if val is None:
        return None
    try:
        text_attr = getattr(val, "text", None)
        if isinstance(text_attr, str) and text_attr.strip():
            return text_attr.strip()
    except Exception:
        pass

    if isinstance(val, dict):
        t = val.get("text")
        if isinstance(t, str) and t.strip():
            return t.strip()

    if isinstance(val, str):
        s = val.strip()
        if not s:
            return None
        # Поищем кусок text='...'
        import re
        m = re.search(r"text\s*=\s*'([^']+)'", s) or re.search(r'text\s*=\s*"([^"]+)"', s)
        if m:
            return m.group(1).strip()
        return s

    d = getattr(val, "__dict__", None)
    if isinstance(d, dict):
        t = d.get("text")
        if isinstance(t, str) and t.strip():
            return t.strip()

    return None

def pick_first_file(call: dict[str, Any]) -> Optional[dict[str, Any]]:
    """
    """
    files = call.get("FILES") or []
    if not isinstance(files, list) or not files:
        return None
    return files[0]

def get_call_status(call: dict[str, Any]) -> str:
    """
    """
    if call.get("SETTINGS", {}).get("MISSED_CALL"):
        return "Пропущенный"
    start = call.get("START_TIME")
    end = call.get("END_TIME")
    completed = call.get("COMPLETED")
    if not end or end == start or completed not in ("Y", "y", True):
        return "Отменённый"
    return "Успешный"


def parse_call_info(call: dict[str, Any]) -> CallInfo:
    """
    """
    start = parse_dt_iso(call.get("START_TIME"))
    end = parse_dt_iso(call.get("END_TIME"))
    direction = {
        "1": "Входящий", 1: "Входящий",
        "2": "Исходящий", 2: "Исходящий",
    }.get(call.get("DIRECTION"), "Неизвестно")
    file_dict = pick_first_file(call)
    return CallInfo(
        id=str(call.get("ID")),
        subject=call.get("SUBJECT"),
        direction=direction,
        start=start,
        end=end,
        duration_human=calculate_duration(start, end),
        status=get_call_status(call),
        file_id=(file_dict or {}).get("id"),
    )

RU_MONTHS = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}

def _format_dt_human(iso: str) -> str:
    """
    Преобразует '2025-08-06T11:43:28+03:00' -> '6 августа 2025, 11:43 (UTC+03:00)'
    """
    dt = datetime.fromisoformat(iso)
    # Часовой пояс в формате UTC±HH:MM
    tz = dt.strftime("%z")  # например '0300'
    tz_str = f"UTC{tz[:3]}:{tz[3:]}" if tz else "UTC"
    return f"{dt.day} {RU_MONTHS[dt.month]} {dt.year}, {dt:%H:%M} ({tz_str})"

def build_call_summary(call: dict[str, Any]) -> str:
    subject = call.get("subject", 'Звонок')
    direction = call.get("direction", "")
    status = call.get("status", "")
    start_iso = call.get("start", "")
    duration = call.get("duration", "")

    date_line = _format_dt_human(start_iso) if start_iso else ""
    trans_val = call.get("transcribation")
    if trans_val is None:
        # TODO ПРОВЕРИТЬ (добавиь лог и отслеживать) иногда могут класть в 'transcription' или 'stt'
        trans_val = call.get("transcription") or call.get("stt")

    transcript_text = _extract_transcription_text(trans_val)

    lines = []
    lines.append(subject)
    if direction:
        lines.append(f"тип: {direction}")
    if date_line:
        lines.append(f"дата: {date_line}")
    if duration:
        lines.append(f"длительность: {duration}")
    if transcript_text:
        lines.append("транскрибация:")
        lines.append(transcript_text)

    return "\n".join(lines)