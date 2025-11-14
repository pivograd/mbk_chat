from agents import Agent, HostedMCPTool, ModelSettings
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions
from openai.types import Reasoning

from classes.config import OpenAIConfig
from openai_agents.tools.ai_send_agent_contact_card import ai_send_agent_contact_card
from openai_agents.utils.insert_main_info_in_prompt import insert_main_info_in_prompt
from settings import MODEL_MAIN, PRODUCT_HELPER_PROMPT_PATH
from utils.read_txt_file import read_txt_file


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

    product_prompt = read_txt_file(PRODUCT_HELPER_PROMPT_PATH)

    product_prompt = insert_main_info_in_prompt(product_prompt, cfg)

    return Agent(
        name="Product Helper Agent",
        model=model,
        handoff_description=(
            "Работает с продуктовым файлом, отвечает клиенту про конкретный проект"
        ),
        tools=[
            ai_send_agent_contact_card,
            mcp
        ],
        instructions=prompt_with_handoff_instructions(product_prompt),
        model_settings=ModelSettings(
            store=True,
            reasoning=Reasoning(
                effort="medium",
            ))
    )

