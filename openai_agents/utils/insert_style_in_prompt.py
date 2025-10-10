from settings import STYLE_BLOCK_PATH
from utils.read_txt_file import read_txt_file


def insert_style_in_prompt(prompt: str) -> str:
    """
    Вставляет содержимое одного текстового файла в другой, вместо заданного блока
    """
    style_block = read_txt_file(STYLE_BLOCK_PATH)
    return prompt.replace('<<COMMUNICATION_STYLE>>', style_block)
