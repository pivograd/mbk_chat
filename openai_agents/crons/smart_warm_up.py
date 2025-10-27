# from chatwoot_api.chatwoot_client import ChatwootClient
# from settings import INBOX_TO_AGENT_CODE, BITRIX_CFG_BY_AGENT_CODE
# from telegram.send_log import send_dev_telegram_log
#
#
# async def smart_warm_up(session: AsyncSession) -> None:
#     active_transports = await TransportActivation.get_active_inboxes(session)
#
#     for inbox_id in active_transports:
#         async with ChatwootClient() as cw:
#             open_ids = await cw.get_open_conversation_ids(inbox_id=inbox_id)
#         agent_code = INBOX_TO_AGENT_CODE.get(inbox_id)
#         if not agent_code:
#             await send_dev_telegram_log(f'[smart_warm_up]\n@pivograd\nТакой херни быть недолжно\nЕсли ты это видишь - ошибка в конфиге!\ninbox_id={inbox_id}\n')
#             # TODO обработка ошибки там, где вызывается функция (в кроне)
#             raise Exception(f"Agent code {inbox_id} not found.")
#
#         funnel_id = BITRIX_CFG_BY_AGENT_CODE.get(agent_code, {}).get('funnel_id')
#         if not funnel_id:
#
#             await send_dev_telegram_log(f'[smart_warm_up]\n@pivograd\nТакой херни быть недолжно\nЕсли ты это видишь - ошибка в конфиге!\ninbox_id={inbox_id}\n')
#             continue
#
#
#
#         for conv_id in open_ids:
#             # Если были сообщения за последние два дня - пропускаем
#             if not await cw.is_stopped_communication(conv_id):
#                 continue