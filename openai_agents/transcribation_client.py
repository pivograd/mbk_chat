from typing import Any

from openai import AsyncOpenAI
from settings import OPENAI_TOKEN, AI_PROXY, TRANSCRIBE_MODEL

from telegram.send_log import send_dev_telegram_log


class TranscribeClient:
    """Класс для работы с Whisper API (транскрибирование аудио)"""

    def __init__(self, api_key: str = OPENAI_TOKEN):
        self.client = AsyncOpenAI(api_key=api_key)
        # self.client = AsyncOpenAI(api_key=api_key, base_url=AI_PROXY)

    async def transcribe(
        self,
        audio_file_path: str,
        model: str = TRANSCRIBE_MODEL,
        language: str = "ru",
    ):
        """
        Возвращает объект транскрипта (ответ SDK).
        """
        try:
            # Откроем файл и НЕ закрываем его, пока не завершится await
            with open(audio_file_path, "rb") as f:
                kwargs = dict(
                    file=f,
                    model=model,
                    language=language,
                )

                transcript = await self.client.audio.transcriptions.create(**kwargs)
                return transcript

        except Exception as e:
            await send_dev_telegram_log(f'[TranscribeClient.transcribe]\nОшибка транскрибации: {e}')
            raise RuntimeError(f"Transcribe error: {type(e).__name__}: {e}") from e

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