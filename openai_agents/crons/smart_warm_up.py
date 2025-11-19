from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from chatwoot_api.chatwoot_client import ChatwootClient
from db.models.bx24_deal import Bx24Deal
from db.models.chatwoot_conversation import ChatwootConversation
from db.models.transport_activation import TransportActivation
from openai_agents.functions.analyze_conversation import analyze_conversation
from settings import INBOX_TO_AGENT_CODE, BITRIX_CFG_BY_AGENT_CODE, but_map_dict
from telegram.send_log import send_dev_telegram_log
from db.models.bx_deal_cw_link import BxDealCwLink
from wazzup_collector_api.check_contact_recent_message import check_contact_recent_message

ignored_inboxes = {18, 14, 13}

async def process_conversation(session: AsyncSession, cw: ChatwootClient, conv_id: int, portal: str, status_to_semantic: dict) -> tuple[bool, str]:
    ...
    try:
        now = datetime.now(timezone.utc)
        if not await cw.is_stopped_communication(conv_id):
            return False, 'Клиент общался с агентом в последнии два дня'
        # 2 Дизъюнкция. Если стадия сделки успешная - пропускаем
        deals_links = await BxDealCwLink.get_deals_for_conversation(session, portal, conv_id)
        has_success_stage = False
        for deal in deals_links:
            status_id = Bx24Deal.get_stage_id(session, deal.bx_deal_id, portal)
            has_success_stage = status_to_semantic.get(status_id) == 'success'
        # TODO добавить стадии с менеджером конкурента и спам
        if has_success_stage:
            return False, 'Успешная стадии сделки в BX24'

        # 3 Если клиент отвечал менеджеру по продажам за последние два дня - пропускаем
        contact_phone = await cw.get_contact_phone_by_conversation(conv_id)
        if not contact_phone:
            await send_dev_telegram_log(f'[smart_warm_up]\nНе удалось найти телефон контакта\nconv_id={conv_id}', 'ERROR')
            return False, 'Не удалось найти телефон контакта'
        if await check_contact_recent_message(contact_phone):
            return False, 'Клиент общался с МОПом в последнии два дня'

        conv = await ChatwootConversation.get_or_create(session, conv_id)
        # 4 Если у клиента назначена встреча с МОПом, и после нее еще не прошло два дня - пропускаем
        if conv.next_meeting_datetime:
            if now <= conv.next_meeting_datetime + timedelta(days=2):
                return False, 'У клиента назначена встреча с МОПом'

        # 5 Если не прошло достаточное колличество дней для рассылки - пропускаем
        try:
            next_warmup_date = conv.get_next_warmup_date()
        except Exception as e:
            await send_dev_telegram_log(f'[smart_warm_up]\nОшибка get_next_warmup_date\nconv_id={conv_id}\nERROR: {e}',
                                        'ERROR')
            return False, 'Ошибка get_next_warmup_date'

        if next_warmup_date and now < next_warmup_date:
            return False, 'Еще не прошло достаточное колличество времени для следующей рассылки'

        # если мы сюда дошли - значит все механические проверки пройдены, можно анализировать диалог
        analyze_resp = await analyze_conversation(conv_id)

        should_send = await analyze_resp.should_send  # TODO если да, то отправляем прогревающее сообшение фиксируем номер рассылки (+1 к warmup_number)
        should_complete = await analyze_resp.should_complete  # TODO если да, то завершаем диалог (не может быть True, если should_send=True)
        next_meeting_datetime = await analyze_resp.next_meeting_datetime  # может быть пустым # TODO если есть, то сохраняем в БД в соответствующее поле

        if next_meeting_datetime:
            # Обновляем дату встречи/звонка
            conv.next_meeting_datetime = next_meeting_datetime

        if should_send:
            await send_warmup_message(conv_id=conv_id)
            # Отправляем прогревающее сообщение
            warmup_number = (conv.warmup_number or 0) + 1
            conv.warmup_number = warmup_number
            conv.last_warmup_date = now

            return True, f'Отправлено прогревающее сообщение. Рассылка {warmup_number}'

        elif should_complete:
            # Завершаем диалог
            await complete_conversation(conv_id=conv_id)
            return False, f'Останавливаем комуникацию с клиентом. Заврешаем диалог: {conv_id}'


    except Exception as e:
        await send_dev_telegram_log(f'[process_conversation]\nКритическая ошибка!\nconv_id={conv_id}\nERROR: {e}','ERROR')
        return False, 'Критическая ошибка в работе функции!'


async def smart_warm_up(session: AsyncSession) -> None:
    active_inboxes = await TransportActivation.get_active_inboxes(session)
    warmup_inboxes = set(active_inboxes) - ignored_inboxes
    async with ChatwootClient() as cw:
        for inbox_id in warmup_inboxes:
            open_ids = await cw.get_open_conversation_ids(inbox_id=inbox_id)
            agent_code = INBOX_TO_AGENT_CODE.get(inbox_id)
            if not agent_code:
                await send_dev_telegram_log(f'[smart_warm_up]\n@pivograd\nТакой херни быть недолжно\nЕсли ты это видишь - ошибка в конфиге!\ninbox_id={inbox_id}\n', 'ERROR')
                continue
            # TODO сделать BitrixConfig , сейчас обычный словарь
            funnel_id = BITRIX_CFG_BY_AGENT_CODE.get(agent_code, {}).get('funnel_id')
            portal = BITRIX_CFG_BY_AGENT_CODE.get(agent_code, {}).get('portal')
            but = but_map_dict.get(portal)
            if not funnel_id or not portal:
                await send_dev_telegram_log(f'[smart_warm_up]\n@pivograd\nТакой херни быть недолжно\nЕсли ты это видишь - ошибка в конфиге!\ninbox_id={inbox_id}\n', 'ERROR')
                continue

            deal_statuses_resp = but.call_api_method('crm.status.list', {'filter': {'ENTITY_ID': f'DEAL_STAGE_{funnel_id}'}}).get('result')
            # МАППИНГ стадий сделки с их группой (успешно/провалено и тд)
            status_to_semantic = {s["STATUS_ID"]: s.get("EXTRA", {}).get("SEMANTICS") for s in deal_statuses_resp}

            for conv_id in open_ids:
                # 1 Если были сообщения в переписке с агентом за последние два дня - пропускаем
                if not await cw.is_stopped_communication(conv_id):
                    continue
                # 2 Дизъюнкция. Если стадия сделки успешная - пропускаем
                deals_links = await BxDealCwLink.get_deals_for_conversation(session, portal, conv_id)
                has_success_stage = False
                for deal in deals_links:
                    status_id = Bx24Deal.get_stage_id(session, deal.bx_deal_id, portal)
                    has_success_stage = status_to_semantic.get(status_id) == 'success'
                # TODO добавить стадии с менеджером конкурента и спам
                if has_success_stage:
                    continue

                # 3 Если клиент отвечал менеджеру по продажам за последние два дня - пропускаем
                contact_phone = await cw.get_contact_phone_by_conversation(conv_id)
                if not contact_phone:
                    await send_dev_telegram_log(f'[smart_warm_up]\nНе удалось найти телефон контакта\nconv_id={conv_id}', 'ERROR')
                    continue
                if await check_contact_recent_message(contact_phone):
                    continue

                conv = await ChatwootConversation.get_or_create(session, conv_id)
                now = datetime.now(timezone.utc)
                # 4 Если у клиента назначена встреча с МОПом, и после нее еще не прошло два дня - пропускаем
                if conv.next_meeting_datetime:
                    if now <= conv.next_meeting_datetime + timedelta(days=2):
                        continue

                # 5 Если не прошло достаточное колличество дней для рассылки - пропускаем
                try:
                    next_warmup_date = conv.get_next_warmup_date()
                except Exception as e:
                    await send_dev_telegram_log(f'[smart_warm_up]\nОшибка get_next_warmup_date\nconv_id={conv_id}\nERROR: {e}','ERROR')
                    continue

                if next_warmup_date and now < next_warmup_date:
                    continue

                # если мы сюда дошли - значит все механические проверки пройдены, можно анализировать диалог
                analyze_resp = await analyze_conversation(conv_id)

                should_send = await analyze_resp.should_send # TODO если да, то отправляем прогревающее сообшение фиксируем номер рассылки (+1 к warmup_number)
                should_complete = await analyze_resp.should_complete # TODO если да, то завершаем диалог (не может быть True, если should_send=True)
                next_meeting_datetime = await analyze_resp.next_meeting_datetime # может быть пустым # TODO если есть, то сохраняем в БД в соответствующее поле

                if next_meeting_datetime:
                    # Обновляем дату встречи/звонка
                    conv.next_meeting_datetime = next_meeting_datetime

                if should_send:
                    # Отправляем прогревающее сообщение
                    warmup_number = (conv.warmup_number or 0) + 1
                    conv.warmup_number = warmup_number
                    conv.last_warmup_date = now

                    await send_warmup_message(conv_id=conv_id)

                elif should_complete:
                    # Завершаем диалог
                    await complete_conversation(conv_id=conv_id)



                q = 1
                d = 2
