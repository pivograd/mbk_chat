import traceback
from urllib.parse import unquote, parse_qsl
import re

from aiohttp import web

from bx24.bx_utils.bitrix_token import BitrixToken
from settings import bau_but, GS_ROISTAT_DEAL_FIELD, gs_but, RP_ROISTAT_DEAL_FIELD, rp_but, river_but, \
    FV_ROISTAT_DEAL_FIELD, fv_but, aerobox_dv_but, ARTCONTEXT_DOMAIN, ARTCONTEXT_WEBHOOK_TOKEN, BX_SOURCE_FIELD
from telegram.send_log import send_telegram_log, send_dev_telegram_log
from utils.get_comment_from_bb_string import get_comment_from_bb_string
from utils.normalize_phone import normalize_phone

portals_mapping = {
    'ГЦК Династия СПб': {
        'roistat': 'ГЦК_Газобетон',
        'funnel_id': 44,
        'token_instance': fv_but,
        'roistat_bx_field': FV_ROISTAT_DEAL_FIELD,
        'source_id': '40',
    },
    'ГЦК ВЗ МСК': {
        'roistat': 'ГЦК_ВЗ МСК',
        'funnel_id': 26,
        'token_instance': fv_but,
        'roistat_bx_field': FV_ROISTAT_DEAL_FIELD,
        'source_id': '42',
    },
    'ГЦК Загородный инженер': {
        'roistat': '',
        'funnel_id': 0,
        'token_instance': aerobox_dv_but,
        'roistat_bx_field': '',
        'source_id': '20',
    },
    'ГЦК ВЗ СПБ': {
        'roistat': 'ГЦК_ВЗ СПБ',
        'funnel_id': 26,
        'token_instance': fv_but,
        'roistat_bx_field': FV_ROISTAT_DEAL_FIELD,
        'source_id': '41',
    },
    'ГЦК Бассейны МСК': {
        'roistat': '',
        'funnel_id': 0,
        'token_instance': river_but,
        'roistat_bx_field': '',
        'source_id': '1',
    },
    'ГЦК Русские Поместья': {
        'roistat': 'ГЦК',
        'funnel_id': 0,
        'token_instance': rp_but,
        'roistat_bx_field': RP_ROISTAT_DEAL_FIELD,
        'source_id': '4',
    },
    'ГЦК Галт Системс': {
        'roistat': 'ГЦК',
        'funnel_id': 18,
        'token_instance': gs_but,
        'roistat_bx_field': GS_ROISTAT_DEAL_FIELD,
        'source_id': '3',
    },
    'ГЦК Баумейстер': {
        'roistat': '',
        'funnel_id': 0,
        'token_instance': bau_but,
        'roistat_bx_field': '',
        'source_id': '2',
    },
}

def is_call_comment(comment: str) -> bool:
    """Проверяет, является ли комментарий звонком."""
    if not comment:
        return False
    markers = ["звонок из сервиса скорозвон", "дата звонка"]
    text = comment.lower()
    return any(marker in text for marker in markers)

async def handle_artcontext_leads(request):
    """
    Обрабатывает исходящий вебхук с Битрикс24 artcontext и создаёт по нему лиды
    """
    try:
        raw_qs = unquote(request.query_string or "")
        params = dict(parse_qsl(raw_qs, keep_blank_values=True))

        name = params.get('name')
        phone = params.get('phone', '')
        lead_id = int(re.sub(r'\D', '', params.get('id', '')))
        source = params.get('source')
        deal_name = name + f' [{source}]'

        # Получаем последний комментарий в таймлайне лида
        but_artcontext = BitrixToken(domain=ARTCONTEXT_DOMAIN, web_hook_auth=ARTCONTEXT_WEBHOOK_TOKEN)
        all_comments = but_artcontext.call_api_method('crm.timeline.comment.list', {'filter': {'ENTITY_ID': lead_id, 'ENTITY_TYPE': 'lead'}, 'select': ['ID', 'CREATED', 'COMMENT']}).get('result')
        last_comment = ''
        for comment in all_comments[::-1]:
            text = comment.get('COMMENT', '')
            if is_call_comment(text):
                last_comment = get_comment_from_bb_string(text)
                break
        portal_data = portals_mapping.get(source, {})
        roistat = portal_data.get('roistat')
        funnel_id = portal_data.get('funnel_id')
        source_id = portal_data.get('source_id')
        roistat_bx_field = portal_data.get('roistat_bx_field')
        but = portal_data.get('token_instance')
        domain = but.domain
        contact_resp = but.call_api_method('crm.duplicate.findbycomm',{'entity_type': 'CONTACT', 'type': 'PHONE','values': [phone]}).get('result')
        if not contact_resp:
            # создаём контакт
            norm_phone = normalize_phone(phone)
            contact_id = but.call_api_method('crm.contact.add', {'fields': {'NAME': name, 'PHONE': [{'VALUE': norm_phone, 'VALUE_TYPE': 'WORK'}]}}).get('result')
            contact_url = f'https://{domain}/crm/contact/details/{contact_id}/'
            await send_telegram_log(f'✅ Создан новый контакт!\nИмя: {name}\nПортал: {domain}\nТелефон: {norm_phone}\nСсылка на контакт: {contact_url}')
        else:
            # берём самый первый контакт
            contact_id = min(contact_resp.get('CONTACT'))

        # создаём новую cделку всегда
        deal_resp = but.call_api_method('crm.deal.add', {'fields': {
            'CONTACT_ID': contact_id, 'TITLE': deal_name, 'COMMENTS': last_comment, 'CATEGORY_ID': funnel_id,
            roistat_bx_field: roistat, BX_SOURCE_FIELD: source_id,
        }})
        deal_id = deal_resp.get('result')
        new_deal_url = f'https://{domain}/crm/deal/details/{deal_id}/'
        success_log_message = f'✅ Создана новая сделка!\nНазвание: {deal_name}\nПортал: {domain}\nID: {deal_id}\nroistat: {roistat}\nИсточник: {source}\nСсылка на сделку: {new_deal_url}'
        await send_telegram_log(success_log_message)
        return web.Response(text="OK", status=200)

    except Exception as e:
        tb = traceback.format_exc()
        await send_telegram_log(f"❌ Ошибка создания сделки: {tb}")
        return web.Response(text=f"Error: {str(e)}", status=500)
