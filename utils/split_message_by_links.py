import re

FILE_LINK_REGEX = r'(http[s]?://[^\s]+?\.(?:pdf|jpe?g|png|docx?|xlsx?|pptx?|txt|csv|gif|webp|mp4|avi|zip|rar))'


def split_message_by_links(message: str) -> list:
    """
    Разбивает большое сообщение на маленькие по ссылкам (файлам)
    """
    parts = re.split(FILE_LINK_REGEX, message, flags=re.IGNORECASE)

    result = []
    for part in parts:
        clean = part.strip().lstrip(')').rstrip('(')
        if clean:
            result.append(clean)
    return result
