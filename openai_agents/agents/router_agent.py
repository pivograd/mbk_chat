from agents import Agent, handoff
from agents.extensions import handoff_filters
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions

from classes.config import OpenAIConfig
from openai_agents.agents.design_agent import build_design_agent
from openai_agents.agents.main_agent import build_general_agent
from openai_agents.agents.manager_agent import build_manager_agent
from openai_agents.agents.mortgage_agent import build_mortgage_agent
from openai_agents.agents.products_agent import build_products_agent
from openai_agents.agents.warmup_agent import build_warmup_agent
from settings import MODEL_MINI, ROUTER_PROMPT_PATH
from utils.read_txt_file import read_txt_file



def build_new_router_agent(cfg: OpenAIConfig) -> Agent:
    general_agent = build_general_agent(cfg.main_prompt_file, cfg.price_complectation, cfg.catalogs_file)
    design_agent = build_design_agent(cfg.design_cost, cfg.price_complectation)
    manager_agent = build_manager_agent(cfg.price_complectation)
    warmup_agent = build_warmup_agent()
    mortgage_agent = build_mortgage_agent(cfg.price_complectation)
    products_agent = build_products_agent(cfg.catalogs_file, cfg.vector_store_id, cfg.price_complectation)

    router_prompt = read_txt_file(ROUTER_PROMPT_PATH).replace('<<PRICE_COMPLECTATION>>', cfg.price_complectation)

    return Agent(
        name=f"Router Agent",
        model=MODEL_MINI,
        handoffs=
        [
            handoff(products_agent, input_filter=handoff_filters.remove_all_tools),
            handoff(general_agent, input_filter=handoff_filters.remove_all_tools),
            handoff(design_agent, input_filter=handoff_filters.remove_all_tools),
            handoff(manager_agent, input_filter=handoff_filters.remove_all_tools),
            handoff(mortgage_agent, input_filter=handoff_filters.remove_all_tools),
            handoff(warmup_agent, input_filter=handoff_filters.remove_all_tools),
        ],
        instructions=prompt_with_handoff_instructions(router_prompt),
    )
