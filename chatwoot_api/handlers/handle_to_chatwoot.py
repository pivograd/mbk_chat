from aiohttp import web

from green_api.handlers.inbound_green_api import inbound_green_api
from wappi.handlers.inbound_wappi import inbound_wappi


async def handle_to_chatwoot(request, agent_code, kind, inbox_id):
    """
    Транспартирует входящее сообщение в Chatwoot
    """

    if kind == "wa":
        return await inbound_green_api(request, agent_code, inbox_id)
    elif kind == "tg":
        return await inbound_wappi(request, agent_code, inbox_id)

    return web.Response(status=404, text=f"Unsupported kind: {kind}")
