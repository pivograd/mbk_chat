from settings import COMPANY_INFO_BLOCK_PATH
from utils.read_txt_file import read_txt_file


def insert_company_info_in_prompt(prompt: str, price_complectation: str) -> str:
    """
    Вставляет содержимое одного текстового файла в другой, вместо заданного блока
    """
    info_block = read_txt_file(COMPANY_INFO_BLOCK_PATH).replace('<<PRICE_COMPLECTATION>>', price_complectation)
    return prompt.replace('<<COMPANY_INFO>>', info_block)
