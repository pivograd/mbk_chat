from agents import Agent

from classes.config import OpenAIConfig
from openai_agents.tools.ai_send_agent_contact_card import ai_send_agent_contact_card
from openai_agents.utils.insert_main_info_in_prompt import insert_main_info_in_prompt
from settings import MODEL_MAIN
from utils.insert_txt_in_block import insert_txt_in_block
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions



def build_main_agent(cfg: OpenAIConfig, model: str = MODEL_MAIN) -> Agent:
    main_prompt = insert_txt_in_block(cfg.main_prompt_file, cfg.catalogs_file, '<<CATALOGS_BLOCK>>')
    main_prompt = insert_main_info_in_prompt(main_prompt, cfg)

    return Agent(
        name="Main Agent",
        model=model,
        handoff_description=(
            "Общается с клиентом по общим вопросам"
        ),
        instructions=prompt_with_handoff_instructions(main_prompt),
        tools=[ai_send_agent_contact_card]
    )