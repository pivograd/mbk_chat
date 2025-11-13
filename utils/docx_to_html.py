import io
import re

import mammoth

# TODO добавить ограничения в 10 листов.


def docx_to_html(docx_bytes: bytes) -> str:
    """

    """
    # Картинки инлайним как data-uri, чтобы xhtml2pdf их видел
    result = mammoth.convert_to_html(
        io.BytesIO(docx_bytes),
        convert_image=mammoth.images.inline(mammoth.images.base64),
    )
    html = result.value
    return re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", html)
