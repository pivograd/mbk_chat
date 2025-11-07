import aiohttp

from telegram.send_log import send_dev_telegram_log


async def get_chat(manager_phone: str, contact_phone: str):
    try:
        url = f'https://wazzup.mbk-chat.ru/api/chat/get?manager_phone={manager_phone}&contact_phone={contact_phone}'
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                return await resp.json()

    except Exception as e:
        await send_dev_telegram_log(f'[get_chat]\nКритическая ошибка\nERROR: {e}', 'ERROR')
        return None
