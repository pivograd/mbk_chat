from agents import function_tool, RunContextWrapper
from aiohttp import web
from sqlalchemy import update

from chatwoot_api.chatwoot_client import ChatwootClient
from db.models.bx_deal_cw_link import BxDealCwLink
from db.models.chatwoot_conversation import ChatwootConversation
from settings import fv_but, FORESTVOLOGDA_DOMAIN
from telegram.send_log import send_dev_telegram_log
from utils.build_contact_info import build_contact_info


@function_tool
async def ai_send_manager_contact_card(ctx: RunContextWrapper[dict]) -> str:
    """
    Отправляет контакт агента клиенту.
    """
    conversation_id = ctx.context.conversation_id
    if not conversation_id:
        await send_dev_telegram_log(f'[ai_send_manager_contact_card]\nВ контексте нет ID диалога.\nctx: {ctx.context}','ERROR')
        return web.json_response({"status": "error"})
    try:
        conversation_id = int(conversation_id)
        await send_dev_telegram_log(f'[ai_send_manager_contact_card]\nЗапрос на отправку контакта менеджера Агентом\nconversation_id: {conversation_id}', 'DEV')
        async with ctx.context.db_session() as session:
            async with session.begin():

                conversation = await ChatwootConversation.get_or_create(session=session, chatwoot_id=conversation_id)

                stmt = (
                    update(ChatwootConversation)
                    .where(
                        ChatwootConversation.id == conversation.id,
                        ChatwootConversation.manager_contact_sent.is_(False),
                    )
                    .values(manager_contact_sent=True)
                    .returning(ChatwootConversation.id)
                )

                result = await session.execute(stmt)
                row = result.first()
                should_send_contact = row is not None

                if not should_send_contact:
                    await send_dev_telegram_log(f'[ai_send_manager_contact_card]\nКонтакт был отправлен ранее!\nconversation_id: {conversation_id}', 'INFO')
                    return web.json_response({"status": "ok"})
                deals = await BxDealCwLink.get_deals_for_conversation(session=session, conversation_id=conversation_id, portal=FORESTVOLOGDA_DOMAIN)
                for deal in deals:
                    deal_id = deal.bx_deal_id
                    break
                if not deal_id:
                    await send_dev_telegram_log(f'[ai_send_manager_contact_card]\nНет deal_id!\ndeals: {deals}', 'DEV')
                    return web.json_response({"status": "error"})

                deal_resp = fv_but.call_api_method('crm.deal.get', {'id': deal_id}).get('result')
                assigned_id = deal_resp.get('ASSIGNED_BY_ID')
                user_resp = fv_but.call_api_method('user.get', {'ID': assigned_id}).get('result', [{}])[0]
                work_phone = user_resp.get('WORK_PHONE')
                if not work_phone:
                    resp = {"success": False, "message": "У ответственного не заполнен рабочий номер телефона!"}
                    return web.json_response(resp, status=200)

                name = user_resp.get('NAME')
                last_name = user_resp.get('LAST_NAME')

                contact_info = build_contact_info(name, last_name, work_phone)
                async with ChatwootClient() as cw:
                    await send_dev_telegram_log(f'[ai_send_manager_contact_card]\nОтправка контакта менеджера!\nconversation_id: {conversation_id}\deal ID: {deal_id}\n contact_info: {contact_info}', 'DEV')
                    await cw.send_message(conversation_id=conversation_id, content=contact_info)

        return web.json_response({"status": "ok"})
    except Exception as e:
        await send_dev_telegram_log(f'[ai_send_manager_contact_card]\nОшибка в tool для отправки контакта!\nconversation_id: {conversation_id}\nERROR: {e}', 'ERROR')
        return web.json_response({"status": "error"})
