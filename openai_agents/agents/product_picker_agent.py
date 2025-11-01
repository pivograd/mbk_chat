from agents import FileSearchTool, Agent
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions

from classes.config import OpenAIConfig
from openai_agents.utils.insert_main_info_in_prompt import insert_main_info_in_prompt
from settings import MODEL_MAIN, PRODUCT_PICKER_PROMPT_PATH
from utils.insert_txt_in_block import insert_txt_in_block


def build_product_picker_agent(cfg: OpenAIConfig,  model: str = MODEL_MAIN) -> Agent:

    product_prompt = insert_txt_in_block(PRODUCT_PICKER_PROMPT_PATH, cfg.catalogs_file, '<<CATALOGS_BLOCK>>')

    product_prompt = insert_main_info_in_prompt(product_prompt, cfg)

    return Agent(
        name="Product Picker Agent",
        model=model,
        handoff_description=(
            "Работает с продуктовым файлом, формирует для клиента подборку проектов."
        ),
        tools=[
            FileSearchTool(
                vector_store_ids=[cfg.vector_store_id],
                max_num_results=5,
            )
        ],
        instructions=prompt_with_handoff_instructions(product_prompt),
)
