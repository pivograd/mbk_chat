from agents import function_tool, RunContextWrapper
from aiohttp import web
from sqlalchemy import update

from chatwoot_api.chatwoot_client import ChatwootClient
from db.models.chatwoot_conversation import ChatwootConversation
from telegram.send_log import send_dev_telegram_log


@function_tool
async def ai_send_agent_contact_card(ctx: RunContextWrapper[dict]) -> str:
    """
    Отправляет контакт агента клиенту.
    """
    conversation_id = ctx.context.conversation_id
    if not conversation_id:
        await send_dev_telegram_log(f'[ai_send_agent_contact_card]\nВ контексте нет ID диалога.\nctx: {ctx.context}','ERROR')
        return web.json_response({"status": "error"})
    try:
        conversation_id = int(conversation_id)

        async with ctx.context.db_session() as session:
            async with session.begin():

                conversation = await ChatwootConversation.get_or_create(session=session, chatwoot_id=conversation_id)

                stmt = (
                    update(ChatwootConversation)
                    .where(
                        ChatwootConversation.id == conversation.id,
                        ChatwootConversation.agent_contact_sent.is_(False),
                    )
                    .values(agent_contact_sent=True)
                    .returning(ChatwootConversation.id)
                )

                result = await session.execute(stmt)
                row = result.first()
                should_send_contact = row is not None

        if not should_send_contact:
            await send_dev_telegram_log(f'[ai_send_agent_contact_card]\nКонтакт был отправлен ранее!\nconversation_id: {conversation_id}', 'INFO')
            return web.json_response({"status": "ok"})

        async with ChatwootClient() as cw:
            await cw.send_message(conversation_id=conversation_id, content='[Мой контакт]')

        return web.json_response({"status": "ok"})
    except Exception as e:
        await send_dev_telegram_log(f'[ai_send_agent_contact_card]\nОшибка в tool для отправки контакта!\nconversation_id: {conversation_id}\nERROR: {e}', 'ERROR')
        return web.json_response({"status": "error"})
