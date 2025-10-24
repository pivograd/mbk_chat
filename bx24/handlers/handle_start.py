from urllib.parse import unquote

import aiohttp_jinja2
from aiohttp import web

@aiohttp_jinja2.template("chat.html")
async def handle_start(request):
    q = 1
    query_string = unquote(request.query_string)
    parts = query_string.split("&")
    params = {}

    for item in parts:
        key, value = item.split("=", 1)
        params[key.strip()] = value.strip()

    return {
        "messages": [],
        "conversation_id": None,
        "domain": None,
        "deal_id": None,
        "links": [],
        "selected_conv_id": None,
        "empty_reason": "Ошибка при загрузке диалога.",
    }
