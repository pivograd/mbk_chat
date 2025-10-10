
from bx24.bx_utils.bitrix_token import BitrixToken


FORESTVOLOGDA_WEBHOOK_TOKEN = '6784/9hs7zngkgvf40of4'
FORESTVOLOGDA_DOMAIN = 'forestvologda.bitrix24.ru'

but = BitrixToken(domain=FORESTVOLOGDA_DOMAIN, web_hook_auth=FORESTVOLOGDA_WEBHOOK_TOKEN)

deals = but.call_list_method('crm.deal.list', {'filter': {'>DATE_MODIFY': '2025-08-21T16:00:00'}, 'select': ['ID', 'TITLE', 'DATE_MODIFY']})

deals_id = [deal.get('ID') for deal in deals]
deals_id_vea = []

deal_id = deals_id[0]
bx_user_id = '6784'
comment_ids = []
for deal_id in deals_id:
    resp = but.call_list_method(
        'crm.timeline.comment.list',
        {
            'filter': {
                'ENTITY_ID': deal_id,
                'ENTITY_TYPE': 'deal',
            },
            'select': ['ID', 'CREATED', 'COMMENT', 'AUTHOR_ID']
        }
    )

    # Фильтруем комментарии
    for comment in resp:
        if comment.get("AUTHOR_ID") == bx_user_id:
            # deals_id_vea.append(deal_id)
            # break
            comment_ids.append(comment.get("ID"))
print('комментов - ' + f'{len(comment_ids)}')
for comment_id in comment_ids:
    r = but.call_api_method('crm.timeline.comment.delete', {'id': int(comment_id)})

