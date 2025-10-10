from pathlib import Path

def insert_txt_in_block(main_file_path: str, inserted_file_path: str, replace_block: str) -> str:
    """
    Вставляет содержимое одного текстового файла в другой, вместо заданного блока
    """
    agent = Path(main_file_path).read_text(encoding="utf-8")
    catalogs = Path(inserted_file_path).read_text(encoding="utf-8").strip()
    return agent.replace(replace_block, catalogs)
