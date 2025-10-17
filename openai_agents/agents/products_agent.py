from agents import FileSearchTool, Agent
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions

from openai_agents.utils.insert_company_info_in_prompt import insert_company_info_in_prompt
from openai_agents.utils.insert_style_in_prompt import insert_style_in_prompt
from settings import MODEL_MAIN, PRODUCT_PROMPT_PATH
from utils.insert_txt_in_block import insert_txt_in_block


def build_products_agent(catalog_file_path: str, vector_store_id: str, price_complectation,  model: str = MODEL_MAIN) -> Agent:

    product_prompt = insert_txt_in_block(PRODUCT_PROMPT_PATH, catalog_file_path, '<<CATALOGS_BLOCK>>')
    product_prompt = insert_style_in_prompt(product_prompt)
    product_prompt = insert_company_info_in_prompt(product_prompt, price_complectation)
    return Agent(
        name="Products Agent",
        model=model,
        handoff_description=(
            "Работает с продуктовым файлом, отвечает клиенту про продукты "
        ),
        tools=[
            FileSearchTool(
                vector_store_ids=[vector_store_id],
                max_num_results=5,
            )
        ],
        instructions=prompt_with_handoff_instructions(product_prompt),
)