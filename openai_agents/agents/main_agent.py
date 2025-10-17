from agents import Agent

from openai_agents.tools.ai_send_agent_contact_card import ai_send_agent_contact_card
from openai_agents.utils.insert_company_info_in_prompt import insert_company_info_in_prompt
from openai_agents.utils.insert_style_in_prompt import insert_style_in_prompt
from settings import MODEL_MAIN
from utils.insert_txt_in_block import insert_txt_in_block
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions



def build_general_agent(file_path: str, price_complectation, catalog_file_path, model: str = MODEL_MAIN) -> Agent:
    # TODO вставляем каталоги динамически
    main_prompt = insert_txt_in_block(file_path, catalog_file_path, '<<CATALOGS_BLOCK>>')
    main_prompt = insert_style_in_prompt(main_prompt)
    main_prompt = insert_company_info_in_prompt(main_prompt, price_complectation)

    return Agent(
        name="General Agent",
        model=model,
        handoff_description=(
            "Общается с клиентом по общим вопросам"
        ),
        instructions=prompt_with_handoff_instructions(main_prompt),
        tools=[ai_send_agent_contact_card]
    )