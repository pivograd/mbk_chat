

def check_message_for_markers(message: str):
    """
    Проверяет содержание сообщения.
    Возвращает True, если в сообщении есть любой из маркеров.
    """
    text = message.lower()

    markers = [
        "звонок", "созвон", "перезвон", "в офис", " бот", "робот", " ии", "позвон",
        "встреча", "встретимся", "встретиться", "о встрече", "позови", "шоурум", "шоу рум",
    ]

    for marker in markers:
        if marker in text:
            return marker

    return None