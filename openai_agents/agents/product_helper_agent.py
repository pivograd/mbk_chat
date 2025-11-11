from agents import FileSearchTool, Agent, HostedMCPTool
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions

from classes.config import OpenAIConfig
from openai_agents.utils.insert_main_info_in_prompt import insert_main_info_in_prompt
from settings import MODEL_MAIN, PRODUCT_HELPER_PROMPT_PATH
from utils.insert_txt_in_block import insert_txt_in_block


def build_product_helper_agent(cfg: OpenAIConfig,  model: str = MODEL_MAIN) -> Agent:

    mcp = HostedMCPTool(tool_config={
        "type": "mcp",
        "server_label": cfg.mcp_lable,
        "allowed_tools": [
            "list_products",
            "get_product",
            "get_product_by_title",
            "search_products",
            "get_media",
            "reload_catalog"
        ],
        "require_approval": "never",
        "server_url": cfg.mcp_server
    })

    product_prompt = insert_txt_in_block(PRODUCT_HELPER_PROMPT_PATH, cfg.catalogs_file, '<<CATALOGS_BLOCK>>')

    product_prompt = insert_main_info_in_prompt(product_prompt, cfg)

    return Agent(
        name="Product Helper Agent",
        model=model,
        handoff_description=(
            "Работает с продуктовым файлом, отвечает клиенту про конкретный проект"
        ),
        tools=[
            mcp
        ],
        instructions=prompt_with_handoff_instructions(product_prompt),
)
