from agents import Agent, handoff
from agents.extensions import handoff_filters
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions

from classes.config import OpenAIConfig
from openai_agents.agents.design_agent import build_design_agent
from openai_agents.agents.main_agent import build_main_agent
from openai_agents.agents.manager_agent import build_manager_agent
from openai_agents.agents.mortgage_agent import build_mortgage_agent
from openai_agents.agents.product_helper_agent import build_product_helper_agent
from openai_agents.agents.product_picker_agent import build_product_picker_agent
from openai_agents.agents.warmup_agent import build_warmup_agent
from settings import MODEL_MINI, ROUTER_PROMPT_PATH
from utils.read_txt_file import read_txt_file



def build_new_router_agent(cfg: OpenAIConfig) -> Agent:
    general_agent = build_main_agent(cfg)
    design_agent = build_design_agent(cfg)
    manager_agent = build_manager_agent(cfg)
    warmup_agent = build_warmup_agent()
    mortgage_agent = build_mortgage_agent(cfg)
    product_helper_agent = build_product_helper_agent(cfg)
    product_picker_agent = build_product_picker_agent(cfg)

    router_prompt = read_txt_file(ROUTER_PROMPT_PATH).replace('<<PRICE_COMPLECTATION>>', cfg.price_complectation)

    return Agent(
        name=f"Router Agent",
        model=MODEL_MINI,
        handoffs=
        [
            handoff(product_helper_agent, input_filter=handoff_filters.remove_all_tools),
            handoff(product_picker_agent, input_filter=handoff_filters.remove_all_tools),
            handoff(general_agent, input_filter=handoff_filters.remove_all_tools),
            handoff(design_agent, input_filter=handoff_filters.remove_all_tools),
            handoff(manager_agent, input_filter=handoff_filters.remove_all_tools),
            handoff(mortgage_agent, input_filter=handoff_filters.remove_all_tools),
            handoff(warmup_agent, input_filter=handoff_filters.remove_all_tools),
        ],
        instructions=prompt_with_handoff_instructions(router_prompt),
    )
