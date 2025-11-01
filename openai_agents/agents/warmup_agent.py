from agents import Agent, FileSearchTool
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions

from settings import MODEL_MINI, WARMUP_PROMPT_PATH
from utils.read_txt_file import read_txt_file


def build_warmup_agent(model: str = MODEL_MINI) -> Agent:
    warmup_prompt = read_txt_file(WARMUP_PROMPT_PATH)
    return Agent(
        name="Warmup Agent",
        model=model,
        handoff_description=(
            "Находит и отправляет полезную информацию про строительство"
        ),
        tools=[
            FileSearchTool(
                vector_store_ids=['vs_68c969d7932c8191a1278f52444d2d04'],
                max_num_results=5,
            )
        ],
        instructions=prompt_with_handoff_instructions(warmup_prompt),
    )
