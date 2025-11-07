from datetime import datetime, timedelta


def formation_contact_correspondence(chats: list[dict]) -> str:
    """
    Cобирает форматированную строку с переписками агентами
    """
    dialogs = []
    for i, chat in enumerate(chats):
        dialog = []
        dialog_header = f'ДИАЛОГ {i+1}! МОП - {chat.get('channel', {}).get('name')}!'
        dialogs.append(dialog_header)
        all_messages = chat.get('messages', [])
        for msg in all_messages:
            sender = f"Менеджер по продажам {i+1}" if msg["direction"] == 1 else "Клиент"

            dt_utc = datetime.fromisoformat(msg["created_at"].replace("Z", "+00:00"))
            dt_msk = dt_utc + timedelta(hours=3)

            formatted_time = dt_msk.strftime("%d.%m.%Y %H:%M")

            text = msg["text"].strip()
            if msg["type"] == "document":
                text = f"(документ) {text}"

            dialog.append(f"[{formatted_time}] {sender}: {text}")

        dialogs.append('\n'.join(dialog))

    return '\n\n'.join(dialogs)