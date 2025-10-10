from agents import Agent
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions

from openai_agents.utils.insert_style_in_prompt import insert_style_in_prompt
from settings import MODEL_MINI, DESIGN_PROMPT_PATH
from utils.read_txt_file import read_txt_file


def build_design_agent(design_cost: str, model: str = MODEL_MINI) -> Agent:
    design_prompt = read_txt_file(DESIGN_PROMPT_PATH).replace('<<DESIGN_COST>>', design_cost)
    design_prompt_with_style = insert_style_in_prompt(design_prompt)
    return Agent(
        name="Design Agent",
        model=model,
        handoff_description=(
            "Рассчитывает индивидуальное проектирование"
        ),
        instructions=prompt_with_handoff_instructions(design_prompt_with_style),
    )