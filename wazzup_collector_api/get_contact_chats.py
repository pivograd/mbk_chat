import aiohttp

from telegram.send_log import send_dev_telegram_log


async def get_contact_chats(contact_phone: str) -> list[dict]:
    try:
        url = f'https://wazzup.mbk-chat.ru/api/contact/chats/history?contact_phone={contact_phone}'
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                data = await resp.json()
                if not data.get('ok'):
                    return data

        return data.get('conversations')

    except Exception as e:
        await send_dev_telegram_log(f'[get_chat]\nКритическая ошибка\nERROR: {e}', 'ERROR')
        return None
