from agents import Agent, HostedMCPTool
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions

from classes.config import OpenAIConfig
from openai_agents.utils.insert_main_info_in_prompt import insert_main_info_in_prompt
from settings import MODEL_MINI, MORTGAGE_PROMPT_PATH
from utils.read_txt_file import read_txt_file


def build_mortgage_agent(cfg: OpenAIConfig, model: str = MODEL_MINI) -> Agent:
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

    mortgage_prompt = read_txt_file(MORTGAGE_PROMPT_PATH)
    mortgage_prompt = insert_main_info_in_prompt(mortgage_prompt, cfg)

    return Agent(
        name="Mortgage Agent",
        model=model,
        handoff_description=(
            "Отвечает про ипотеку и её оформление"
        ),
        instructions=prompt_with_handoff_instructions(mortgage_prompt),
        tools=[
            mcp
        ],
    )
