from datetime import datetime, timedelta

import aiohttp

from telegram.send_log import send_dev_telegram_log


async def get_chat_history(manager_phone: str, contact_phone: str) -> list[str]:
    try:
        url = f'https://wazzup.mbk-chat.ru/api/chat/history?manager_phone={manager_phone}&contact_phone={contact_phone}'
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                data = await resp.json()

        messages = data.get('messages', [])

        dialog = []
        for msg in messages:
            sender = "Менеджер по продажам" if msg["direction"] == 1 else "Клиент"

            # парсим время и прибавляем 3 часа (МСК)
            dt_utc = datetime.fromisoformat(msg["created_at"].replace("Z", "+00:00"))
            dt_msk = dt_utc + timedelta(hours=3)

            formatted_time = dt_msk.strftime("%d.%m.%Y %H:%M")

            text = msg["text"].strip()
            if msg["type"] == "document":
                text = f"(документ) {text}"

            dialog.append(f"[{formatted_time}] {sender}: {text}")
        return dialog
    except Exception as e:
        await send_dev_telegram_log(f'[get_chat_history]\nКритическая ошибка\nERROR: {e}', 'ERROR')
        return []

    # https: // wazzup.mbk - chat.ru / chat / history?manager_phone = 79261237106 & contact_phone = 79035172010