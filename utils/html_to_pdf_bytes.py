import io
from pathlib import Path

from xhtml2pdf import pisa
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


FONT_DIR = Path(__file__).resolve().parent / "fonts"
FONT_FILE = FONT_DIR / "DejaVuSans.ttf"

if not FONT_FILE.exists():
    raise RuntimeError(f"Не найден файл шрифта: {FONT_FILE}")

# ВАЖНО: регистрируем шрифт под именем Helvetica
pdfmetrics.registerFont(TTFont("Helvetica", str(FONT_FILE)))


def html_to_pdf_bytes(html_body: str, title: str = "Document") -> bytes:
    html_full = f"""<!doctype html>
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
<title>{title}</title>
<style>
 @page {{
    size: A4;
    margin: 1.5cm;
 }}
 body {{
    /* используем Helvetica, но это уже твой DejaVuSans */
    font-family: "Helvetica";
    font-size: 10pt;
 }}
 h1,h2,h3 {{ page-break-after: avoid; }}
 table {{ border-collapse: collapse; width: 100%; table-layout: fixed; }}
 th, td {{ border: 1px solid #999; padding: 4px; word-wrap: break-word; }}
 img {{ max-width: 100%; height: auto; }}
 pre, code {{ white-space: pre-wrap; word-wrap: break-word; }}
 .page-break {{ page-break-before: always; }}
</style>
</head>
<body>
{html_body}
</body>
</html>"""

    buf = io.BytesIO()
    result = pisa.CreatePDF(
        src=html_full,
        dest=buf,
        encoding="utf-8",
    )
    if result.err:
        raise RuntimeError(f"Ошибка генерации PDF (xhtml2pdf). Код ошибки: {result.err}")
    return buf.getvalue()
