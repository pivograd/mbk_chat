import traceback

import requests
from typing import Dict, Any, Optional

from classes.config import WAConfig
from settings import AGENTS_BY_CODE
from telegram.send_log import send_dev_telegram_log
from utils.normalize_phone import normalize_phone

def _build_contact_payload(
        client_phone: str,
        contact_phone: str,
        first_name: str = None,
        last_name: str = None
        ) -> Dict[str, Any]:
    chat_id = f"{normalize_phone(client_phone)[1:]}@c.us"
    contact = {"phoneContact": normalize_phone(contact_phone)[1:],}
    if first_name:
        contact["firstName"] = first_name
    if last_name:
        contact["lastName"] = last_name

    return {"chatId": chat_id, "contact": contact}


async def send_contact(
        first_name: str,
        last_name: str,
        contact_phone: str,
        client_phone: str,
        agent_name: Optional[str] = None,
        wa_config: Optional[WAConfig] = None
):
    """
    Отправляет контакт клиенту в WhatsApp через Green API.
    """
    try:
        if agent_name:
            wa_config = AGENTS_BY_CODE[agent_name].get_wa_cfg()

        base_url, instance_id, api_token = wa_config.get_green_api_params()

        url = f"{base_url}/waInstance{instance_id}/sendContact/{api_token}"
        payload = _build_contact_payload(client_phone=client_phone, contact_phone=contact_phone, first_name=first_name, last_name=last_name)

        headers = {"Content-Type": "application/json"}

        resp = requests.post(url, json=payload, headers=headers)
        ok = 200 <= resp.status_code < 300

        return ok

    except Exception as e:
        tb = traceback.format_exc()
        await send_dev_telegram_log(f'[green-api.send_contact_to_client]\nОшибка при отправке контакта клиенту: {tb}', log_level='ERROR')
        return False


async def green_api_send_agent_contact(wa_config, agent_phone, client_phone):
    """
    Отправляет контакт клиенту в WhatsApp через Green API.
    """
    base_url, instance_id, api_token = wa_config.get_green_api_params()
    url = f"{base_url}/waInstance{instance_id}/sendContact/{api_token}"
    payload = _build_contact_payload(client_phone=client_phone, contact_phone=agent_phone)
    headers = {"Content-Type": "application/json"}

    return requests.post(url, json=payload, headers=headers)
