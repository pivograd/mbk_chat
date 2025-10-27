from agents import Agent
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions

from classes.config import OpenAIConfig
from openai_agents.utils.insert_company_info_in_prompt import insert_company_info_in_prompt
from openai_agents.utils.insert_style_in_prompt import insert_style_in_prompt
from settings import MODEL_MINI, MORTGAGE_PROMPT_PATH
from utils.read_txt_file import read_txt_file


def build_mortgage_agent(cfg: OpenAIConfig, model: str = MODEL_MINI) -> Agent:
    mortgage_prompt = read_txt_file(MORTGAGE_PROMPT_PATH)
    mortgage_prompt = insert_style_in_prompt(mortgage_prompt)
    mortgage_prompt = insert_company_info_in_prompt(mortgage_prompt, cfg)

    return Agent(
        name="Mortgage Agent",
        model=model,
        handoff_description=(
            "Отвечает про ипотеку и её оформление"
        ),
        instructions=prompt_with_handoff_instructions(mortgage_prompt),
    )