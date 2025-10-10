import traceback

from aiohttp import web

from avito_api import get_chat_partner_id, get_inbox_token, get_avito_item_url
from avito_api.utils.parse_avito_item import parse_avito_ad
from chatwoot_api.chatwoot_client import ChatwootClient, ChatwootError
from telegram.send_log import send_dev_telegram_log


async def handle_avito_webhook(request):
    """Обработчик вебхука Авито"""
    try:
        inbox_id = int(request.match_info.get('inbox_id'))
        avito_token = get_inbox_token(inbox_id)
    except (TypeError, ValueError):
        return web.json_response({"error": "Invalid inbox_id"}, status=400)

    data = await request.json()
    payload = data.get('payload', {})
    # смотрим тип
    if payload.get('type', '') == 'message':
        message_data = payload.get('value', {})
        chat_id = message_data.get('chat_id')
        item_id = message_data.get('item_id')
        user_id = message_data.get('user_id')  # ID нашего пользователя Avito
        author_id = message_data.get('author_id') # ID клиента avito
        message_text = message_data.get('content', {}).get('text', '')
        message_type = 0
        if author_id == user_id:
            message_type = 1
            author_id = get_chat_partner_id(avito_token, user_id, chat_id)

        try:
            async with ChatwootClient() as cw:
                chatwoot_contact_id, _ = await cw.get_or_create_contact(f'AVITO {user_id}-{author_id}', author_id) # TODO возвращать tuple у метода как с диалогами
                source_id = f"{user_id}.{chat_id}"
                conversation_id, created = await cw.get_or_create_conversation(chatwoot_contact_id, inbox_id, source_id)
                if created:
                    # получаем ссылку на объявление
                    # item_url = get_avito_item_url(avito_token, user_id, item_id)
                    # item_info = await parse_avito_ad(item_url) # TODO доработать парсинг инфы про объявление
                    ...

                last_message = await cw.get_last_message_text(conversation_id)
                if last_message == message_text:
                    return web.json_response({"status": "ignored"})
                await cw.send_message(conversation_id, message_text, message_type=message_type)
            return web.json_response({"status": "ok"})
        except ChatwootError as e:
            tb = traceback.format_exc()
            await send_dev_telegram_log(f'[handle_avito_webhook] Ошибка при отправке сообщения в chatwoot: {tb}\n\n\nPAYLOAD: {payload}')
            return web.json_response({"error": "Ошибка при отправке в chatwoot"}, status=400)

    else:
        # TODO реализовать синхронизацию не только текстовых сообщений payload.get('type')
        return web.json_response({"status": "ignored"})
