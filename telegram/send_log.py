import aiohttp

TELEGRAM_TOKEN = "8351683768:AAHOQAReauI5av_-YaxxqEgiex2rhBHTWaY"
TELEGRAM_CHAT_ID = "-4878653504"
TELEGRAM_MY_CHAT_ID = "-4814382081"

TG_ERROR_CHAT_ID = '-4835185182'
TG_WARNING_CHAT_ID = '-4877221490'
TG_INFO_CHAT_ID = '-4904204139'
TG_DEV_CHAT_ID = '-4656654185'
TG_WARMUP_CHAT_ID = '-4936591349'
TG_AGENTS_CHAT_ID = '-4985524072'
TG_MANAGERS_CHAT_ID = '-4702575929'
TG_STATUS_CHAT_ID = '-4936343919'

def get_chat_id(log_level):
    if log_level == "ERROR":
        return TG_ERROR_CHAT_ID
    elif log_level == "WARNING":
        return TG_WARNING_CHAT_ID
    elif log_level == "DEV":
        return TG_DEV_CHAT_ID
    elif log_level == "WARMUP":
        return TG_WARMUP_CHAT_ID
    elif log_level == "AGENTS":
        return TG_AGENTS_CHAT_ID
    elif log_level == "MANAGERS":
        return TG_MANAGERS_CHAT_ID
    elif log_level == "STATUS":
        return TG_STATUS_CHAT_ID
    else:
        return TG_INFO_CHAT_ID

async def send_telegram_log(message: str):
    """Отправка сообщения в Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=payload) as resp:
            if resp.status != 200:
                print(f"Ошибка отправки лога в ТГ: {await resp.text()}")


TG_MESSAGE_LIMIT = 4096

async def send_dev_telegram_log(message: str, log_level: str = 'INFO'):
    """Отправка сообщения в Telegram с обрезкой, если превышает лимит."""
    try:
        if len(message) > TG_MESSAGE_LIMIT:
            message = message[:TG_MESSAGE_LIMIT - 150] + "\n... [обрезано]"

        chat_id = get_chat_id(log_level)

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=payload) as resp:
                if resp.status != 200:
                    print(f"Ошибка отправки лога в ТГ: {await resp.text()}. СООБЩЕНИЕ: {message}")
    except Exception as e:
        print('Ошибка при отправке лога(')
        raise e

async def safe_log(msg, level='DEV'):
    try:
        await send_dev_telegram_log(msg, level)
    except Exception as e:
        # Безусловный дубль в stdout, чтобы точно увидеть хоть что-то
        print(f"[send_dev_telegram_log FAILED] level={level} msg={msg} error={e}", flush=True)
