from classes.config import OpenAIConfig
from settings import COMPANY_INFO_BLOCK_PATH
from utils.read_txt_file import read_txt_file


def insert_company_info_in_prompt(prompt: str, cfg: OpenAIConfig) -> str:
    """
    Вставляет содержимое одного текстового файла в другой, вместо заданного блока
    """
    info_block = read_txt_file(COMPANY_INFO_BLOCK_PATH).replace('<<PRICE_COMPLECTATION>>', cfg.price_complectation)
    info_block = info_block.replace('<<FOUNDATION_SIZE>>', cfg.foundation_size)
    info_block = info_block.replace('<<GLUED_BEAM_SIZE>>', cfg.glued_beam_size)
    return prompt.replace('<<COMPANY_INFO>>', info_block)
