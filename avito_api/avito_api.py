import requests

from avito_api.avito_settings import AVITO_INBOX_MAPPING



AVITO_OAUTH_URL = "https://api.avito.ru/token/"
AVITO_SUBSCRIBE_URL = "https://api.avito.ru/messenger/v3/webhook"
AVITO_UNSUBSCRIBE_URL = "https://api.avito.ru/messenger/v1/webhook/unsubscribe"
AVITO_SUBS_WEBHOOKS = 'https://api.avito.ru/messenger/v1/subscriptions'


DOMAIN = 'http://185.239.142.177:5019'
WEBHOOK = f'{DOMAIN}/webhook/v3/avito'
# TODO нужно реализовать через ООП (написать класс AvitoClient)
def get_avito_token(client_id: str, client_secret: str) -> str:
    """
    Функция для получения токена авито
    """
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }
    response = requests.post(AVITO_OAUTH_URL, data=data)
    response.raise_for_status()
    return response.json()["access_token"]

def get_inbox_token(inbox_id: int):
    """Получает токен авито по id источника chatwoot"""
    settings = AVITO_INBOX_MAPPING.get(inbox_id)
    client_id = settings.get("client_id")
    client_secret = settings.get("client_secret")
    return get_avito_token(client_id, client_secret)


def subscribe_avito(token: str, webhook_url: str) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "url": webhook_url
    }
    response = requests.post(AVITO_SUBSCRIBE_URL, headers=headers, json=data)
    response.raise_for_status()
    return response.json()


def unsubscribe_avito(token: str, webhook_url: str) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "url": webhook_url
    }
    response = requests.post(AVITO_UNSUBSCRIBE_URL, headers=headers, json=data)
    response.raise_for_status()
    return response.json()


def get_avito_subscriptions(token: str) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    response = requests.post(AVITO_SUBS_WEBHOOKS, headers=headers)
    response.raise_for_status()
    return response.json()


def send_message_to_avito(token: str, user_id: str, chat_id: str, text: str) -> dict:
    """
    Отправляет сообщение в чат Avito.
    """
    url = f"https://api.avito.ru/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "type": "text",
        "message": {
            "text": text
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()


def get_avito_chats(token: str, user_id: str, limit: int = 20, offset: int = 0) -> dict:
    """
    Получает список чатов пользователя Avito.
    """
    url = f"https://api.avito.ru/messenger/v2/accounts/{user_id}/chats"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    params = {
        "limit": limit,
        "offset": offset
    }

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()

import requests

def get_avito_chat_info(token: str, user_id: str, chat_id: str) -> dict:
    """
    Получает информацию про указанный чат Avito .
    """
    url = f"https://api.avito.ru/messenger/v2/accounts/{user_id}/chats/{chat_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def get_chat_partner_id(token, user_id, chat_id):
    """
    Получает из информации про чат ID пользователя.
    """
    chat_response = get_avito_chat_info(token, user_id, chat_id)
    for user in chat_response.get("users", []):
        if user.get("id") != user_id:
            return user.get("id")
    return None


def get_last_message(token, user_id, chat_id) -> str:
    """
    Получает последнее сообщение в диалоге AVITO
    """
    chat_response = get_avito_chat_info(token, user_id, chat_id)
    last_message = chat_response.get('last_message', {}).get('content', {}).get('text', '')
    return last_message



def get_avito_item_info(token: str, user_id: int, item_id: int) -> dict:
    """
    Получает информацию об объявлении Avito.
    """
    url = f"https://api.avito.ru/core/v1/accounts/{user_id}/items/{item_id}/"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def get_avito_item_url(token: str, user_id: int, item_id: int) -> str | None:
    """
    Возвращает публичную ссылку на объявление (поле 'url') или None.
    """
    data = get_avito_item_info(token, user_id, item_id)
    return data.get("url")
