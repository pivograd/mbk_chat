from agents import function_tool, RunContextWrapper
from aiohttp import web

from chatwoot_api.chatwoot_client import ChatwootClient
from telegram.send_log import send_dev_telegram_log


@function_tool
async def ai_send_agent_contact_card(ctx: RunContextWrapper[dict]) -> str:
    """
    Отправляет контакт агента клиенту.
    """
    conversation_id = ctx.context.get("conversation_id")
    if not conversation_id:
        await send_dev_telegram_log(f'[ai_send_agent_contact_card]\nВ контексте нет ID диалога.\nctx: {ctx.context}')
        return web.json_response({"status": "ok"})
    async with ChatwootClient() as cw:
        await cw.send_message(conversation_id=conversation_id, content='[Мой контакт]')

    return web.json_response({"status": "ok"})
