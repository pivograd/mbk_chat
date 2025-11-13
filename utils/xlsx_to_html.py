import re
import io
import pandas as pd
from openpyxl import load_workbook

# TODO упростить
# TODO добавить ограничения в 1 лист(sheets) и 500 строк

def xlsx_to_html(xlsx_bytes: bytes, include_formulas=True, include_comments=True) -> str:
    # Читаем все листы как таблицы (значения)
    xls = pd.ExcelFile(io.BytesIO(xlsx_bytes), engine="openpyxl")
    parts: list[str] = []
    for sheet in xls.sheet_names:
        df = xls.parse(sheet_name=sheet, dtype=str)
        # пустые nan → ""
        df = df.fillna("")
        parts.append(f"<h2>{sheet}</h2>")
        parts.append(df.to_html(index=False, border=1, escape=True))

    # Дополнительно вытащим формулы и комментарии (если нужны)
    if include_formulas or include_comments:
        wb = load_workbook(io.BytesIO(xlsx_bytes), data_only=False, read_only=True)
        if include_formulas:
            formula_items = []
            for ws in wb.worksheets:
                for row in ws.iter_rows():
                    for c in row:
                        # формула — строка, начинающаяся с '='
                        try:
                            if isinstance(c.value, str) and c.value.startswith("="):
                                formula_items.append(
                                    f"<tr><td>{ws.title}</td><td>{c.coordinate}</td><td><code>{c.value}</code></td></tr>"
                                )
                        except Exception as e:
                            pass
            if formula_items:
                parts.append("<h3>Формулы</h3>")
                parts.append("<table border='1'><tr><th>Лист</th><th>Адрес</th><th>Формула</th></tr>")
                parts.extend(formula_items)
                parts.append("</table>")

        if include_comments:
            comment_items = []
            for ws in wb.worksheets:
                for row in ws.iter_rows():
                    for c in row:
                        try:
                            if c.comment:
                                txt = (c.comment.text or "").replace("\n", "<br>")
                                comment_items.append(
                                    f"<tr><td>{ws.title}</td><td>{c.coordinate}</td><td>{txt}</td></tr>"
                                )
                        except Exception as e:
                            pass
            if comment_items:
                parts.append("<h3>Комментарии</h3>")
                parts.append("<table border='1'><tr><th>Лист</th><th>Адрес</th><th>Комментарий</th></tr>")
                parts.extend(comment_items)
                parts.append("</table>")

    html = "\n".join(parts)
    return re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", html)
