import pathlib
from dotenv import load_dotenv

from bx24.handlers.handle_deal_update import handle_deal_update
from chatwoot_api.handlers.handle_from_chatwoot import handle_from_chatwoot
from chatwoot_api.handlers.handle_to_chatwoot import handle_to_chatwoot
from company_websites.handlers.handle_lead_on_site import handle_lead_on_site
from trust_me import trust_me

env_path = pathlib.Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

import pathlib
from functools import partial

import aiohttp_jinja2
import jinja2
from aiohttp import web
from bx24.handlers.handle_artcontext_leads import handle_artcontext_leads
from bx24.handlers.handle_bx24_customfield_dialog import handle_bx24_customfield_dialog, \
    handle_bx24_customfield_dialog_send_contact, handle_bx24_customfield_select_dialog
from bx24.handlers.handle_message_bitrix_webhook import handle_message_bitrix_webhook
from company_websites.handlers.handle_form_website_webhook import handle_form_website_webhook
from db.core import init_db, close_db, setup_workers, _cleanup_workers
from db.migrate import alembic_upgrade_head
from settings import BOTS_CFG, CLIENT_MAX_SIZE
from openai_agents.handlers.handle_sdk_agent_webhook import handle_sdk_agent_webhook

app = web.Application(client_max_size=CLIENT_MAX_SIZE)
BASE_DIR = pathlib.Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"

aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)))
# Website
app.router.add_post("/webhook/v3/website", handle_form_website_webhook)
app.router.add_post("/webhook/leadon/website", handle_lead_on_site)

app.router.add_post("/trust/me", trust_me)
# BX24
app.router.add_post("/bx24/mbkchat/start", handle_message_bitrix_webhook)
app.router.add_post("/bx24/transport/leads", handle_artcontext_leads)
app.router.add_post("/bx24/deal/update", handle_deal_update)

app.router.add_post("/bx24/mbkchat/chat", handle_bx24_customfield_dialog)
app.router.add_post("/bx24/mbkchat/send_contact", handle_bx24_customfield_dialog_send_contact)
app.router.add_post("/bx24/mbkchat/select_dialog", handle_bx24_customfield_select_dialog)


# OpenAI
app.router.add_post("/sdk_agent_webhook/{agent_code}", handle_sdk_agent_webhook)

# Chatwoot handlers
for agent_cfg in BOTS_CFG:
    for transport in agent_cfg.transports:
        app.router.add_post(
            f"/{agent_cfg.agent_code}/{transport.kind}/to/chatwoot/{transport.chatwoot.inbox_id}",
            partial(handle_to_chatwoot, agent_code=agent_cfg.agent_code, kind=transport.kind, inbox_id=transport.chatwoot.inbox_id)
        )
        app.router.add_post(
            f"/{agent_cfg.agent_code}/{transport.kind}/from/chatwoot/{transport.chatwoot.inbox_id}",
            partial(handle_from_chatwoot, agent_code=agent_cfg.agent_code, kind=transport.kind, inbox_id=transport.chatwoot.inbox_id)
        )

alembic_upgrade_head()
app.on_startup.append(init_db)
app.on_startup.append(setup_workers)
app.on_cleanup.append(close_db)
app.on_shutdown.append(_cleanup_workers)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=5019)
