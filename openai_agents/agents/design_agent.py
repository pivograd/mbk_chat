from agents import Agent
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions

from openai_agents.utils.insert_company_info_in_prompt import insert_company_info_in_prompt
from openai_agents.utils.insert_style_in_prompt import insert_style_in_prompt
from settings import MODEL_MINI, DESIGN_PROMPT_PATH
from utils.read_txt_file import read_txt_file


def build_design_agent(design_cost: str, price_complectation, model: str = MODEL_MINI) -> Agent:
    # TODO сделать общий метод для конфигурации промта, чтобы потом править все в одном месте.
    design_prompt = read_txt_file(DESIGN_PROMPT_PATH).replace('<<DESIGN_COST>>', design_cost)
    design_prompt = insert_style_in_prompt(design_prompt)
    design_prompt = insert_company_info_in_prompt(design_prompt, price_complectation)
    return Agent(
        name="Design Agent",
        model=model,
        handoff_description=(
            "Рассчитывает индивидуальное проектирование"
        ),
        instructions=prompt_with_handoff_instructions(design_prompt),
    )