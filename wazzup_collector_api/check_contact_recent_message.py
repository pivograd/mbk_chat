import aiohttp

from telegram.send_log import send_dev_telegram_log


async def check_contact_recent_message(contact_phone: str) -> bool | None:
    """
    Проверяет, есть ли хотя бы одно входящее сообщение от контакта за последние 2 дня.
    """
    url = f"https://wazzup.mbk-chat.ru/api/contact/chats/has_recent_client_message?contact_phone={contact_phone}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                # 404 — контакт не найден
                if resp.status == 404:
                    return None

                resp.raise_for_status()
                data = await resp.json()

        if not data.get("ok"):
            await send_dev_telegram_log(f"[check_contact_recent_message]\nНекорректный ответ API: {data}","ERROR")
            return None

        return bool(data.get("has_recent_client_message"))

    except Exception as e:
        await send_dev_telegram_log(f"[check_contact_recent_message]\nКритическая ошибка\nERROR: {e}","ERROR")
        return None
