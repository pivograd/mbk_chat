

def build_contact_info(name: str, last_name: str, phone: str) -> str:
    """
    Формирует сообщение определенного формата для Chatwoot с информацией про контакт
    """

    return (f"[Менеджер по строительству]\n"
           f"Имя: {name}\n"
           f"Фамилия: {last_name}\n"
           f"Телефон: {phone}\n")
