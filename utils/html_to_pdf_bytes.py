import io
from xhtml2pdf import pisa

def html_to_pdf_bytes(html_body: str, title: str = "Document") -> bytes:
    html_full = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
 body {{ font-family: "DejaVu Sans", "Arial Unicode MS", Helvetica, Arial, sans-serif; font-size: 10pt; }}
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
    result = pisa.CreatePDF(src=html_full, dest=buf, encoding="utf-8")
    if result.err:
        raise RuntimeError("Ошибка генерации PDF (xhtml2pdf). Упростите HTML/таблицы или разобьёте по частям.")
    return buf.getvalue()