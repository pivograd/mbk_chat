import os

from dotenv import load_dotenv

from bx24.bx_utils.bitrix_token import BitrixToken
from classes.config import AgentCfg, OpenAIConfig, WAConfig, ChatwootBinding, TGConfig

load_dotenv()
CLIENT_MAX_SIZE = 1024**2 * 30 # 30 МБ
AI_PROXY = 'http://150.241.122.84:3333/v1/'
# Bitrix24
PORTAL_AGENTS = {
    'forestvologda.bitrix24.ru': {
        '26': 'maksim',
        '60': 'pavel',
    },
}

BITRIX_CFG_BY_AGENT_CODE = {
    'maksim': {
        'portal': 'forestvologda.bitrix24.ru',
        'funnel_id': '26'
    },
    'pavel': {
        'portal': 'forestvologda.bitrix24.ru',
        'funnel_id': '60'
    }
}

BX_SOURCE_FIELD = 'SOURCE_ID'

# BX артконтекст
ARTCONTEXT_WEBHOOK_TOKEN = os.getenv('ARTCONTEXT_WEBHOOK_TOKEN')
ARTCONTEXT_DOMAIN = os.getenv('ARTCONTEXT_DOMAIN')
art_but = BitrixToken(domain=ARTCONTEXT_DOMAIN, web_hook_auth=ARTCONTEXT_WEBHOOK_TOKEN)

# BX аэробокс (загородный инженер)
AEROBOX_DV_WEBHOOK_TOKEN = os.getenv('AEROBOX_DV_WEBHOOK_TOKEN')
AEROBOX_DV_DOMAIN = os.getenv('AEROBOX_DV_DOMAIN')
aerobox_dv_but = BitrixToken(domain=AEROBOX_DV_DOMAIN, web_hook_auth=AEROBOX_DV_WEBHOOK_TOKEN)

# BX форествологда
FORESTVOLOGDA_WEBHOOK_TOKEN = os.getenv('FORESTVOLOGDA_WEBHOOK_TOKEN')
FORESTVOLOGDA_DOMAIN = os.getenv('FORESTVOLOGDA_DOMAIN')
FV_ROISTAT_DEAL_FIELD = 'UF_CRM_1706175291'
FV_MBK_DIALOG_BOOL_FIELD = 'UF_CRM_1757401004551'
fv_but = BitrixToken(domain=FORESTVOLOGDA_DOMAIN, web_hook_auth=FORESTVOLOGDA_WEBHOOK_TOKEN)

# BX русские поместья
RP_WEBHOOK_TOKEN = os.getenv('RP_WEBHOOK_TOKEN')
RP_DOMAIN = os.getenv('RP_DOMAIN')
RP_ROISTAT_DEAL_FIELD = 'UF_CRM_1742463504913'
rp_but = BitrixToken(domain=RP_DOMAIN, web_hook_auth=RP_WEBHOOK_TOKEN)

# BX бассейны
RIVER_POOLS_WEBHOOK_TOKEN = os.getenv('RIVER_POOLS_WEBHOOK_TOKEN')
RIVER_POOLS_DOMAIN = os.getenv('RIVER_POOLS_DOMAIN')
river_but = BitrixToken(domain=RIVER_POOLS_DOMAIN, web_hook_auth=RIVER_POOLS_WEBHOOK_TOKEN)

# BX галтсистем
GS_WEBHOOK_TOKEN = os.getenv('GS_WEBHOOK_TOKEN')
GS_DOMAIN = os.getenv('GS_DOMAIN')
GS_ROISTAT_DEAL_FIELD = ''
gs_but = BitrixToken(domain=GS_DOMAIN, web_hook_auth=GS_WEBHOOK_TOKEN)

# BX баумейстер
BAUMEISTER_WEBHOOK_TOKEN = os.getenv('BAUMEISTER_WEBHOOK_TOKEN')
BAUMEISTER_DOMAIN = os.getenv('BAUMEISTER_DOMAIN')
bau_but = BitrixToken(domain=BAUMEISTER_DOMAIN, web_hook_auth=BAUMEISTER_WEBHOOK_TOKEN)

but_map_dict = {
    FORESTVOLOGDA_DOMAIN: fv_but,
}

# Database
DATABASE_USER = os.getenv('DATABASE_USER')
DATABASE_PASSWORD=os.getenv('DATABASE_PASSWORD')
DATABASE_NAME=os.getenv('DATABASE_NAME')
#DEV
# DATABASE_USER = 'postgres'
# DATABASE_PASSWORD= 'vea'
# DATABASE_NAME='mbkchat'

DATABASE_URL = f'postgresql+asyncpg://{DATABASE_USER}:{DATABASE_PASSWORD}@127.0.0.1:5432/{DATABASE_NAME}'

# OPENAI
OPENAI_TOKEN = os.getenv('OPENAI_TOKEN')
from agents import set_default_openai_key
set_default_openai_key(OPENAI_TOKEN)
MODEL_MAIN = "gpt-5.1"
MODEL_MINI = "gpt-5-mini"
TRANSCRIBE_MODEL = "gpt-4o-transcribe"

SERVER_PROMPT_PATH = '/opt/mbk/mbk_chat/openai_agents/prompts'
STYLE_BLOCK_PATH = f"{SERVER_PROMPT_PATH}/reusable/style.txt"
MAIN_BLOCK_PATH = f"{SERVER_PROMPT_PATH}/reusable/main_info.txt"
COMPANY_INFO_BLOCK_PATH = f"{SERVER_PROMPT_PATH}/reusable/company_info.txt"
DESIGN_PROMPT_PATH = f"{SERVER_PROMPT_PATH}/reusable/design_agent.txt"
MANAGER_PROMPT_PATH = f"{SERVER_PROMPT_PATH}/reusable/manager_agent.txt"
MORTGAGE_PROMPT_PATH = f"{SERVER_PROMPT_PATH}/reusable/mortgage_agent.txt"
PRODUCT_HELPER_PROMPT_PATH = f"{SERVER_PROMPT_PATH}/reusable/product_helper_agent.txt"
PRODUCT_PICKER_PROMPT_PATH = f"{SERVER_PROMPT_PATH}/reusable/product_picker_agent.txt"
ROUTER_PROMPT_PATH = f"{SERVER_PROMPT_PATH}/reusable/router_agent.txt"
WARMUP_PROMPT_PATH = f"{SERVER_PROMPT_PATH}/reusable/warmup_agent.txt"

# CHATWOOT
CHATWOOT_API_TOKEN = os.getenv('CHATWOOT_API_TOKEN')
CHATWOOT_HOST = os.getenv('CHATWOOT_HOST')
CHATWOOT_ACCOUNT_ID = os.getenv('CHATWOOT_ACCOUNT_ID')

AI_OPERATOR_CHATWOOT_IDS = [13, 14]

# Главный конфиг с Агентами

BOTS_CFG: list[AgentCfg] = [
    AgentCfg(
        agent_code="maksim",
        cw_token=os.getenv('MAKSIM_CW_BOT_TOKEN'),
        name="Максим",
        openai=OpenAIConfig(
            vector_store_id="vs_6891ca7fab5481919070e9974947b2f8",
            main_prompt_file=f"{SERVER_PROMPT_PATH}/agents_instructions/main_maksim.txt",
            catalogs_file=f"{SERVER_PROMPT_PATH}/agents_instructions/catalogs/maksim_catalogs.txt",
            design_cost="45 000",
            price_complectation="Базовая комплектация",
            glued_beam_size="160х190 мм",
            foundation_size="(150х150 мм / L - 3000 мм)",
            agent_name="Максим",
            agent_card="https://ii.mbk-chat.ru/viz_maksim.jpg",
            warranty="30 лет",
            geography="Санкт-Петербург, Ленинградская область + граничащие области (Карелия, Новгородская, Псковская и Вологодская области)",
            office_address="метро Технологический институт, Измайловский проспект, д.7",
            website="https://вологодскоезодчество.рф",
            mcp_file_name="products-spb.json",
            mcp_server="https://ii.mbk-chat.ru/mcp-spb",
            mcp_lable="VZ_Catalog_SPB",
            telephone_number="+78122411934",
        ),
        transports=[
            WAConfig(
                instance_id=os.getenv('MAKSIM1_GREEN_API_INSTANCE_ID'),
                api_token=os.getenv('MAKSIM1_GREEN_API_TOKEN'),
                chatwoot=ChatwootBinding(
                    inbox_id=3,
                    assignee_id='14',
                )
            ),
            WAConfig(
                instance_id=os.getenv('MAKSIM2_GREEN_API_INSTANCE_ID'),
                api_token=os.getenv('MAKSIM2_GREEN_API_TOKEN'),
                chatwoot=ChatwootBinding(
                    inbox_id=15,
                    assignee_id='14',
                )
            ),
            WAConfig(
                instance_id=os.getenv('MAKSIM3_GREEN_API_INSTANCE_ID'),
                api_token=os.getenv('MAKSIM3_GREEN_API_TOKEN'),
                chatwoot=ChatwootBinding(
                    inbox_id=17,
                    assignee_id='14',
                )
            ),
            TGConfig(
                api_token=os.getenv('MAKSIM_WAPPI_API_TOKEN'),
                instance_id=os.getenv('MAKSIM_WAPPI_INSTANCE_ID'),
                chatwoot=ChatwootBinding(
                    inbox_id=12,
                    assignee_id='14',
                )
            )
        ],
    ),
    AgentCfg(
        agent_code="pavel",
        cw_token=os.getenv('PAVEL_CW_BOT_TOKEN'),
        name="Павел",
        openai=OpenAIConfig(
            vector_store_id="vs_68dbcc7b5a348191803d1a2de2e7b0b8",
            main_prompt_file=f"{SERVER_PROMPT_PATH}/agents_instructions/main_pavel.txt",
            catalogs_file=f"{SERVER_PROMPT_PATH}/agents_instructions/catalogs/pavel_catalogs.txt",
            design_cost="50 000",
            price_complectation="Теплый контур",
            glued_beam_size="200х190 мм",
            foundation_size="(200х200 мм / L - 3000 мм)",
            agent_name="Павел",
            agent_card="https://ii.mbk-chat.ru/viz_Pavel.jpg",
            warranty="25 лет",
            geography="Москва и Московская область + граничащие области (Тверская, Ярославская, Владимирская, Рязанская, Тульская, Калужская, Смоленская)",
            office_address="Дмитровское шоссе, 81",
            website="https://москва.вологодскоезодчество.рф",
            mcp_file_name="products-msk.json",
            mcp_server="https://ii.mbk-chat.ru/mcp-msk",
            mcp_lable="VZ_Catalog_MSK",
            telephone_number="+74959759847",
        ),
        transports=[
            WAConfig(
                instance_id=os.getenv('PAVEL_GREEN_API_INSTANCE_ID'),
                api_token=os.getenv('PAVEL_GREEN_API_TOKEN'),
                chatwoot=ChatwootBinding(
                    inbox_id=4,
                    assignee_id='13',
                )
            ),
            WAConfig(
                instance_id=os.getenv('PAVEL2_GREEN_API_INSTANCE_ID'),
                api_token=os.getenv('PAVEL2_GREEN_API_TOKEN'),
                chatwoot=ChatwootBinding(
                    inbox_id=16,
                    assignee_id='13',
                )
            ),
            WAConfig(
                instance_id=os.getenv('PAVEL3_GREEN_API_INSTANCE_ID'),
                api_token=os.getenv('PAVEL3_GREEN_API_TOKEN'),
                chatwoot=ChatwootBinding(
                    inbox_id=19,
                    assignee_id='13',
                )
            ),
            TGConfig(
                api_token=os.getenv('PAVEL_WAPPI_API_TOKEN'),
                instance_id=os.getenv('PAVEL_WAPPI_INSTANCE_ID'),
                chatwoot=ChatwootBinding(
                    inbox_id=11,
                    assignee_id='13',
                )
            )
        ],
    ),
    AgentCfg(
        agent_code="test",
        name="МБК Guard",
        cw_token=os.getenv('PAVEL_CW_BOT_TOKEN'),
        openai=OpenAIConfig(
            vector_store_id="vs_68dbcc7b5a348191803d1a2de2e7b0b8",
            main_prompt_file=f"{SERVER_PROMPT_PATH}/agents_instructions/main_pavel.txt",
            catalogs_file=f"{SERVER_PROMPT_PATH}/agents_instructions/catalogs/pavel_catalogs.txt",
            design_cost="50 000",
            price_complectation="Теплый контур",
            glued_beam_size="200х190 мм",
            foundation_size="(200х200 мм / L - 3000 мм)",
            agent_name="Павел",
            agent_card="https://ii.mbk-chat.ru/viz_Pavel.jpg",
            warranty="25 лет",
            geography="Москва и Московская область + граничащие области (Тверская, Ярославская, Владимирская, Рязанская, Тульская, Калужская, Смоленская)",
            office_address="Дмитровское шоссе, 81",
            website="https://москва.вологодскоезодчество.рф",
            mcp_file_name="products-msk.json",
            mcp_server="https://ii.mbk-chat.ru/mcp-msk",
            mcp_lable="VZ_Catalog_MSK",
            telephone_number="+74959759847",
        ),
        transports=[
            TGConfig(
                api_token=os.getenv('TEST_WAPPI_API_TOKEN'),
                instance_id=os.getenv('TEST_WAPPI_INSTANCE_ID'),
                chatwoot=ChatwootBinding(
                    inbox_id=13,
                    assignee_id='13',
                )
            ),
            WAConfig(
                instance_id=os.getenv('MBK_GUARD_GREEN_API_INSTANCE_ID'),
                api_token=os.getenv('MBK_GUARD_GREEN_API_TOKEN'),
                chatwoot=ChatwootBinding(
                    inbox_id=14,
                    assignee_id='2',
                )
            )
        ],
    ),
    AgentCfg(
        agent_code="leadon",
        name="LEADON",
        cw_token=os.getenv('PAVEL_CW_BOT_TOKEN'),
        openai=OpenAIConfig(
            vector_store_id="vs_68dbcc7b5a348191803d1a2de2e7b0b8",
            main_prompt_file=f"{SERVER_PROMPT_PATH}/agents_instructions/main_pavel.txt",
            catalogs_file=f"{SERVER_PROMPT_PATH}/agents_instructions/catalogs/pavel_catalogs.txt",
            design_cost="50 000",
            price_complectation="Теплый контур",
            glued_beam_size="200х190 мм",
            foundation_size="(200х200 мм / L - 3000 мм)",
            agent_name="Павел",
            agent_card="https://ii.mbk-chat.ru/viz_Pavel.jpg",
            warranty="25 лет",
            geography="Москва и Московская область + граничащие области (Тверская, Ярославская, Владимирская, Рязанская, Тульская, Калужская, Смоленская)",
            office_address="Дмитровское шоссе, 81",
            website="https://москва.вологодскоезодчество.рф",
            mcp_file_name="products-msk.json",
            mcp_server="https://ii.mbk-chat.ru/mcp-msk",
            mcp_lable="VZ_Catalog_MSK",
            telephone_number="+74959759847",
        ),
        transports=[
            WAConfig(
                instance_id=os.getenv('LEADON_GREEN_API_INSTANCE_ID'),
                api_token=os.getenv('LEADON_GREEN_API_TOKEN'),
                chatwoot=ChatwootBinding(
                    inbox_id=18,
                    assignee_id='13',
                )
            )
        ],
    ),
]

AGENTS_BY_CODE: dict[str, AgentCfg] = {a.agent_code: a for a in BOTS_CFG}
INBOX_TO_TRANSPORT = {t.chatwoot.inbox_id: t for agent in BOTS_CFG for t in agent.transports}

AGENT_TO_INBOX_IDS: dict[str, list[int]] = {
    agent.agent_code: [
        t.chatwoot.inbox_id
        for t in agent.transports
        if getattr(t, "chatwoot", None) and getattr(t.chatwoot, "inbox_id", None) is not None
    ]
    for agent in BOTS_CFG
}

INBOX_TO_AGENT_CODE: dict[int, str] = {
    t.chatwoot.inbox_id: agent.agent_code
    for agent in BOTS_CFG
    for t in agent.transports
    if getattr(t, "chatwoot", None) and getattr(t.chatwoot, "inbox_id", None) is not None
}

 # TODO: чем больше мап - тем больше цена ошибки коллизии, в будущем нужна надежная защита