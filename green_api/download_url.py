import aiohttp

from classes.config import WAConfig
from telegram.send_log import send_dev_telegram_log


async def greenapi_download_url(session: aiohttp.ClientSession, wa_config: WAConfig, chat_id: str, id_message: str):
    """
    Вызывает GreenAPI /downloadFile и возвращает (download_url, file_name) или None.
    """
    url = f"{wa_config.base_url}/waInstance{wa_config.instance_id}/downloadFile/{wa_config.api_token}"
    payload = {"chatId": chat_id, "idMessage": id_message}
    async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        if resp.status != 200:
            text = await resp.text()
            await send_dev_telegram_log(f"[GreenAPI downloadFile] HTTP {resp.status}: {text}", "ERROR")
            return None
        data = await resp.json()
        download_url = data.get("downloadUrl")
        file_name = data.get("fileName") or "audio.oga"
        if not download_url:
            await send_dev_telegram_log(f"[GreenAPI downloadFile] Нет downloadUrl в ответе: {data}", "ERROR")
            return None
        return download_url, file_name
