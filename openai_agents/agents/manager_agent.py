from agents import Agent
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions

from classes.config import OpenAIConfig
from openai_agents.utils.insert_main_info_in_prompt import insert_main_info_in_prompt
from settings import MODEL_MINI, MANAGER_PROMPT_PATH
from utils.read_txt_file import read_txt_file

def build_manager_agent(cfg: OpenAIConfig, model: str = MODEL_MINI) -> Agent:

    manager_prompt = read_txt_file(MANAGER_PROMPT_PATH)
    manager_prompt = insert_main_info_in_prompt(manager_prompt, cfg)


    return Agent(
        name="Manager Agent",
        model=model,
        handoff_description=(
            "Передаёт клиента менеджеру по строительству"
        ),
        instructions=prompt_with_handoff_instructions(manager_prompt),
    )
