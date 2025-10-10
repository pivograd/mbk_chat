from agents import Agent

from openai_agents.tools.ai_send_agent_contact_card import ai_send_agent_contact_card
from openai_agents.utils.insert_style_in_prompt import insert_style_in_prompt
from settings import MODEL_MAIN
from utils.read_txt_file import read_txt_file
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions



def build_general_agent(file_path: str, model: str = MODEL_MAIN) -> Agent:
    main_prompt = read_txt_file(file_path)
    main_prompt_with_style = insert_style_in_prompt(main_prompt)
    return Agent(
        name="General Agent",
        model=model,
        handoff_description=(
            "Общается с клиентом по общим вопросам"
        ),
        instructions=prompt_with_handoff_instructions(main_prompt_with_style),
        tools=[ai_send_agent_contact_card]
    )