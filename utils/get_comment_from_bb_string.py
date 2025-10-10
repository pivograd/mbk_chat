import re


def get_comment_from_bb_string(bb_string):
    """Парсит комментарий оператора из BB строки"""
    pattern = r'\[B\]\s*Комментарий\s*:\s*\[/B\]\s*(.*?)(?=\[B\]|$)'
    match = re.search(pattern, bb_string, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return match.group(1).strip()
