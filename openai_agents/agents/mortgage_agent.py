from agents import Agent
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions

from openai_agents.utils.insert_style_in_prompt import insert_style_in_prompt
from settings import MODEL_MINI, MORTGAGE_PROMPT_PATH
from utils.read_txt_file import read_txt_file


def build_mortgage_agent(model: str = MODEL_MINI) -> Agent:
    mortgage_prompt = read_txt_file(MORTGAGE_PROMPT_PATH)
    mortgage_prompt_with_style = insert_style_in_prompt(mortgage_prompt)
    return Agent(
        name="Mortgage Agent",
        model=model,
        handoff_description=(
            "Отвечает про ипотеку и её оформление"
        ),
        instructions=prompt_with_handoff_instructions(mortgage_prompt_with_style),
    )