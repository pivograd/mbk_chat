from classes.config import OpenAIConfig
from settings import MAIN_BLOCK_PATH
from utils.insert_txt_in_block import insert_txt_in_block
from utils.read_txt_file import read_txt_file


def insert_main_info_in_prompt(prompt: str, cfg: OpenAIConfig) -> str:
    """
    Подставляет в промт основную информацию на место <<MAIN_INFO>>
    """
    main_block = read_txt_file(MAIN_BLOCK_PATH)
    catalogs = read_txt_file(cfg.catalogs_file)

    main_block = main_block.replace( '<<CATALOGS_BLOCK>>', catalogs)
    main_block = main_block.replace('<<PRICE_COMPLECTATION>>', cfg.price_complectation)
    main_block = main_block.replace('<<FOUNDATION_SIZE>>', cfg.foundation_size)
    main_block = main_block.replace('<<GLUED_BEAM_SIZE>>', cfg.glued_beam_size)
    main_block = main_block.replace('<<AGENT_NAME>>', cfg.agent_name)
    main_block = main_block.replace('<<AGENT_CARD>>', cfg.agent_card)
    main_block = main_block.replace('<<WARRANTY>>', cfg.warranty)
    main_block = main_block.replace('<<GEOGRAPHY>>', cfg.geography)
    main_block = main_block.replace('<<OFFICE_ADDRESS>>', cfg.office_address)
    main_block = main_block.replace('<<WEBSITE>>', cfg.website)
    main_block = main_block.replace('<<TELEPHONE NUMBER>>', cfg.telephone_number)

    return prompt.replace('<<MAIN_INFO>>', main_block)
