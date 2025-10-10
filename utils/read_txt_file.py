
def read_txt_file(file_path: str) -> str:
    """Читает текстовый файл и возвращает его содержимое в виде строки."""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()
