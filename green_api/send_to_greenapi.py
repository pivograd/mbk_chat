import requests
import re

from settings import INBOX_TO_TRANSPORT
from utils.split_message_by_links import split_message_by_links, FILE_LINK_REGEX


def send_to_greenapi(bot_name, phone, message, inbox_id):
    """
    Отправляет сообщение в WhatsApp через Green API
    """
    # Получаем конфигурацию бота
    wa_config = INBOX_TO_TRANSPORT.get(inbox_id)
    base_url, instance_id, api_token = wa_config.get_green_api_params()
    # Формируем ID чата для WhatsApp
    chat_id = f"{phone}@c.us"
    headers = {'Content-Type': 'application/json'}
    messages = split_message_by_links(message)

    for msg in messages:
        msg_stripped = msg.lstrip(".,!? \t;:-") .strip()
        if not len(msg_stripped) > 1:
            continue
        if re.match(FILE_LINK_REGEX, msg_stripped, re.IGNORECASE):
            # ссылка на файл
            payload_file = {
                "chatId": chat_id,
                "urlFile": msg_stripped,
                "fileName": msg_stripped.split('/')[-1],
            }
            url_file = f"{base_url}/waInstance{instance_id}/sendFileByUrl/{api_token}"
            requests.post(url_file, headers=headers, json=payload_file)
        else:
            # обычный текст
            payload_text = {
                "chatId": chat_id,
                "message": msg_stripped
            }
            url_text = f"{base_url}/waInstance{instance_id}/sendMessage/{api_token}"
            requests.post(url_text, headers=headers, json=payload_text)
