from agents import Agent
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions

from classes.config import OpenAIConfig
from openai_agents.utils.insert_main_info_in_prompt import insert_main_info_in_prompt
from settings import MODEL_MINI, DESIGN_PROMPT_PATH
from utils.read_txt_file import read_txt_file


def build_design_agent(cfg: OpenAIConfig, model: str = MODEL_MINI) -> Agent:
    design_prompt = read_txt_file(DESIGN_PROMPT_PATH).replace('<<DESIGN_COST>>', cfg.design_cost)
    design_prompt = insert_main_info_in_prompt(design_prompt, cfg)
    return Agent(
        name="Design Agent",
        model=model,
        handoff_description=(
            "Рассчитывает индивидуальное проектирование"
        ),
        instructions=prompt_with_handoff_instructions(design_prompt),
    )