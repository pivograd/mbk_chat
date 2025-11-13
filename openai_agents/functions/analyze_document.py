import base64
import os
import re
from pathlib import Path
from datetime import datetime

import aiofiles
from openai import AsyncOpenAI

from settings import OPENAI_TOKEN, MODEL_MAIN
from telegram.send_log import send_dev_telegram_log
from utils.docx_to_html import docx_to_html
from utils.download_bytes import download_bytes
from utils.html_to_pdf_bytes import html_to_pdf_bytes
from utils.xlsx_to_html import xlsx_to_html

DOCUMENT_PROMPT = """
Ты — эксперт по сжатому изложению документов. Твоя задача — внимательно ПРОЧИТАТЬ ВЕСЬ документ и выдать краткое описание на русском языке.

Цель ответа: 3–4 абзаца связного текста (без пунктов/списков), передающих суть документа.

Правила уровня детализации (адаптация к размеру):

- Если документ маленький (≈1–5 страниц) — включай больше конкретики: ключевые факты, цифры, определения, выводы автора, 2–4 наиболее важные детали/примеры.
- Если документ средний (≈6–20 страниц) — баланс: главная идея + 2–3 ключевых тезиса/аргумента, минимально необходимых деталей.
- Если документ большой (20+ страниц) — только высокоуровневое ядро: тема, цель/вопрос, структура, 3–5 основных выводов/рекомендаций или направлений; подробности не перечисляй.

Объём ответа ВСЕГДА ограничен 3–4 абзацами независимо от объёма документа.

Что учитывать при чтении:

Игнорируй оглавление, футеры/хедеры, повторяющиеся колонтитулы, страницы «Спасибо», юридические дисклеймеры, баннеры.
Если есть аннотация/резюме/введение/заключение — используй их как опорные, но проверь содержимое по телу документа.
Если есть разделы/главы — улови их логику: цель → метод/подход → результаты/аргументы → выводы/импликации.
Числа/метрики/сроки упоминай только если они действительно определяют суть (не более 2–3 штук в сумме).

Не добавляй сведений, которых нет в документе. Не фантазируй.

Формат выхода (строго):

Русский язык.
3–4 абзаца прозы.

Без маркированных списков, заголовков, ссылок, цитат, метакомментариев и фраз типа «в документе говорится».
Без упоминания этого задания и метаданных.

Поведение в крайних случаях:

Если текст нечитаем/пуст/сильно повреждён — верни: «Документ недоступен для осмысленного суммирования.»
Если документ на другом языке — всё равно выдай саммари на русском. Названия собственные сохраняй в оригинале.
Критерии самопроверки перед ответом:

(1) Передана главная тема и цель?
(2) Выделены ключевые выводы/тезисы?
(3) Уровень детализации соответствует размеру?
(4) Ровно 3–4 абзаца, без списков и служебных фраз?
""".strip()

ROOT_SAVE_DIR = Path("./_saved_docs").resolve()

def _slug(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^\w\-\.]+", "-", s, flags=re.U)
    s = re.sub(r"-{2,}", "-", s)
    return s.strip("-") or "document"

def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

async def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

async def _async_write_bytes(path: Path, data: bytes) -> None:
    await _ensure_dir(path.parent)
    async with aiofiles.open(path, "wb") as f:
        await f.write(data)

async def _async_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    await _ensure_dir(path.parent)
    async with aiofiles.open(path, "w", encoding=encoding) as f:
        await f.write(text)

async def analyze_document(document_url: str, model: str = MODEL_MAIN) -> str:
    """
    1) Скачивает файл по URL (aiohttp внутри download_bytes).
    2) Если PDF — сразу отправляем base64 в OpenAI.
       Если DOCX/XLSX — конвертируем: DOCX→HTML через mammoth, XLSX→HTML через pandas/openpyxl.
    3) HTML → PDF (xhtml2pdf), отправляем base64 в OpenAI Responses.
    4) Перед отправкой сохраняем артефакты в ./_saved_docs/: исходник, HTML (если был), итоговый PDF.
    5) Возвращаем текст саммари.
    """
    ext = Path(document_url).suffix.lower()
    raw = await download_bytes(document_url)

    # — подготовка путей сохранения
    base_name = _slug(Path(document_url).name or "document")
    stamp = _ts()
    base_dir = ROOT_SAVE_DIR / f"{base_name}__{stamp}"
    original_path = base_dir / f"{base_name}{ext or ''}"
    html_path = base_dir / f"{base_name}.html"
    pdf_path = base_dir / f"{base_name}.pdf"

    # — сохраняем исходник сразу
    try:
        await _async_write_bytes(original_path, raw)
    except Exception as e:
        await send_dev_telegram_log(f"[analyze_document] Не удалось сохранить оригинал: {original_path} -> {e}")

    # — конвертация к PDF
    html: str | None = None
    if ext == ".pdf":
        pdf_bytes = raw
    elif ext in (".docx",):
        html = docx_to_html(raw)
        pdf_bytes = html_to_pdf_bytes(html, title=os.path.basename(document_url) or "DOCX")
    elif ext in (".xlsx", ".xls"):
        html = xlsx_to_html(raw, include_formulas=True, include_comments=True)
        pdf_bytes = html_to_pdf_bytes(html, title=os.path.basename(document_url) or "XLSX")
    else:
        # Попытка эвристик: DOCX → затем XLSX
        tried = []
        try:
            html = docx_to_html(raw)
            pdf_bytes = html_to_pdf_bytes(html, title="Document")
        except Exception as e1:
            tried.append(f"DOCX:{e1}")
            try:
                html = xlsx_to_html(raw, include_formulas=True, include_comments=True)
                pdf_bytes = html_to_pdf_bytes(html, title="Workbook")
            except Exception as e2:
                tried.append(f"XLSX:{e2}")
                await send_dev_telegram_log(f"[analyze_document] Неподдерживаемый формат. Попытки: {', '.join(tried)}")
                raise RuntimeError(f"Неподдерживаемый формат. Попытки: {', '.join(tried)}")

    # — если был HTML — сохраним для отладки
    if html is not None:
        try:
            await _async_write_text(html_path, html)
        except Exception as e:
            await send_dev_telegram_log(f"[analyze_document] Не удалось сохранить HTML: {html_path} -> {e}")

    # — сохраняем итоговый PDF (всегда)
    try:
        await _async_write_bytes(pdf_path, pdf_bytes)
    except Exception as e:
        await send_dev_telegram_log(f"[analyze_document] Не удалось сохранить PDF: {pdf_path} -> {e}")

    await send_dev_telegram_log(
        "[analyze_document] Сохранено:\n"
        f"— Оригинал: {original_path}\n"
        f"— HTML: {html_path if html is not None else '—'}\n"
        f"— PDF: {pdf_path}"
    )

    # — отправка в OpenAI
    base64_string = base64.b64encode(pdf_bytes).decode("ascii")
    client = AsyncOpenAI(api_key=OPENAI_TOKEN)
    content_items = [
        {
            "type": "input_file",
            "filename": pdf_path.name,
            "file_data": f"data:application/pdf;base64,{base64_string}",
        }
    ]

    resp = await client.responses.create(
        model=model,
        instructions=DOCUMENT_PROMPT,
        input=[{"role": "user", "content": content_items}],
    )
    return resp.output_text
