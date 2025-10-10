

def get_phone_variants(phone: str) -> list[str]:
    """Возвращает список с разными варинтами написания номера телефона"""
    digits = ''.join(c for c in phone if c.isdigit() or c == '+')
    if digits.startswith('+7'):
        base = digits[2:]
    elif digits.startswith('8') or digits.startswith('7'):
        base = digits[1:]
    else:
        base = digits
    if not base:
        return []

    return [f'+7{base}', f'7{base}', f'8{base}']
