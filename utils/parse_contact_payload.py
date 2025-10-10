def parse_contact_message(message: str) -> tuple[str, str, str]:
    """
    Парсит сообщение формата build_contact_info и достает имя, фамилию и телефон.
    """
    lines = message.strip().splitlines()
    name, last_name, phone = "", "", ""

    for line in lines:
        if line.startswith("Имя:"):
            name = line.replace("Имя:", "").strip()
        elif line.startswith("Фамилия:"):
            last_name = line.replace("Фамилия:", "").strip()
        elif line.startswith("Телефон:"):
            phone = line.replace("Телефон:", "").strip()

    return name, last_name, phone
