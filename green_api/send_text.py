import traceback
import requests
from typing import Dict, Any, Optional

from classes.config import WAConfig
from settings import AGENTS_BY_CODE
from telegram.send_log import send_dev_telegram_log
from utils.normalize_phone import normalize_phone


def _build_message_payload(client_phone: str, message: str) -> Dict[str, Any]:
    chat_id = f"{normalize_phone(client_phone)[1:]}@c.us"
    return {
        "chatId": chat_id,
        "message": message
    }


async def send_text_message(message: str, client_phone: str, agent_name: Optional[str] = None, wa_config: Optional[WAConfig] = None) -> bool:
    """
    Отправляет текстовое сообщение клиенту в WhatsApp через Green API.
    """
    try:
        if agent_name:
            wa_config = AGENTS_BY_CODE[agent_name].get_wa_cfg()

        base_url, instance_id, api_token = wa_config.get_green_api_params()

        url = f"{base_url}/waInstance{instance_id}/sendMessage/{api_token}"
        payload = _build_message_payload(client_phone=client_phone, message=message)

        headers = {"Content-Type": "application/json"}

        resp = requests.post(url, json=payload, headers=headers)
        ok = 200 <= resp.status_code < 300

        return ok

    except Exception:
        tb = traceback.format_exc()
        await send_dev_telegram_log(
            f'[green-api.send_message_to_client]\nОшибка при отправке сообщения клиенту: {tb}',
            log_level='ERROR'
        )
        return False

