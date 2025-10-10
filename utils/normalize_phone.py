import re

def normalize_phone(phone: str) -> str:
    """
    Приводит номер телефона к формату +7XXXXXXXXXX.
    """
    # Убираем всё, кроме цифр
    digits = re.sub(r"\D", "", phone)

    # Если начинается с 8 или 7, то меняем на +7
    if digits.startswith("8") or digits.startswith("7"):
        digits = "+7" + digits[1:]

    return digits
