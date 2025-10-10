from chatwoot_api.chatwoot_client import ChatwootClient, ChatwootError
from classes.config import ChatwootBinding
from telegram.send_log import send_dev_telegram_log
from utils.normalize_phone import normalize_phone


async def safe_send_to_chatwoot(phone, name, message, cw_cfg: ChatwootBinding, comment = None, message_type = 1):
    """
    Отправляет сообщение от клиента в Chatwoot
    """

    inbox_id = cw_cfg.inbox_id

    phone = normalize_phone(phone)
    identifier = phone.lstrip("+")
    assignee_id = cw_cfg.assignee_id

    try:
        async with ChatwootClient() as cw:
            contact_id, _ = await cw.get_or_create_contact(name=name, identifier=identifier, phone=phone)
            conversation_id, _ = await cw.get_or_create_conversation(contact_id=contact_id, inbox_id=inbox_id, assignee_id=assignee_id)
            if comment:
                await cw.send_message(conversation_id=conversation_id, content=comment, message_type=message_type, private=True)
            resp = await cw.send_message(conversation_id=conversation_id, content=message, message_type=message_type)
            return resp
    except ChatwootError as e:
        await send_dev_telegram_log(f'[safe_send_to_chatwoot] Ошибка при отправке сообщения в chatwoot: {e}', 'ERROR')
        return None
