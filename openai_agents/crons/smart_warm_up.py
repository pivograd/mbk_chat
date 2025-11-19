import traceback
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession

from chatwoot_api.chatwoot_client import ChatwootClient
from db.models.bx24_deal import Bx24Deal
from db.models.chatwoot_conversation import ChatwootConversation
from db.models.transport_activation import TransportActivation
from openai_agents.classes.conversation_result import ConversationResult
from openai_agents.classes.smart_warmup_status import SmartWarmupStats
from openai_agents.functions.analyze_conversation import analyze_conversation
from settings import INBOX_TO_AGENT_CODE, BITRIX_CFG_BY_AGENT_CODE, but_map_dict
from telegram.send_log import send_dev_telegram_log
from db.models.bx_deal_cw_link import BxDealCwLink
from wazzup_collector_api.check_contact_recent_message import check_contact_recent_message

ignored_inboxes = {18, 14, 13}

async def process_conversation(session: AsyncSession, cw: ChatwootClient, conv_id: int, portal: str, status_to_semantic: dict) -> ConversationResult:
    """
    """
    try:
        now = datetime.now(timezone.utc)
        if not await cw.is_stopped_communication(conv_id):
            return ConversationResult(
                conv_id=conv_id,
                status='skipped',
                message='Клиент общался с агентом в последние два дня'
            )
        # 2 Дизъюнкция. Если стадия сделки успешная - пропускаем
        deals_links = await BxDealCwLink.get_deals_for_conversation(session, portal, conv_id)
        for deal in deals_links:
            status_id = await Bx24Deal.get_stage_id(session, deal.bx_deal_id, portal)
            if status_to_semantic.get(status_id) == 'success':
                return ConversationResult(
                    conv_id=conv_id,
                    status='skipped',
                    message='Успешная стадия сделки в BX24'
                )

        # TODO добавить стадии с менеджером конкурента и спам

        # 3 Если клиент отвечал менеджеру по продажам за последние два дня - пропускаем
        contact_phone = await cw.get_contact_phone_by_conversation(conv_id)
        if not contact_phone:
            await send_dev_telegram_log(f'[smart_warm_up]\nНе удалось найти телефон контакта\nconv_id={conv_id}', 'ERROR')
            return ConversationResult(
                conv_id=conv_id,
                status='error',
                message='Не удалось найти телефон контакта'
            )
        if await check_contact_recent_message(contact_phone):
            return ConversationResult(
                conv_id=conv_id,
                status='skipped',
                message='Клиент общался с МОПом в последние два дня'
            )

        conv = await ChatwootConversation.get_or_create(session, conv_id)
        # 4 Если у клиента назначена встреча с МОПом, и после нее еще не прошло два дня - пропускаем
        if conv.next_meeting_datetime:
            if now <= conv.next_meeting_datetime + timedelta(days=2):
                return ConversationResult(
                    conv_id=conv_id,
                    status='skipped',
                    message='У клиента назначена встреча с МОПом'
                )

        # 5 Если не прошло достаточное колличество дней для рассылки - пропускаем
        try:
            next_warmup_date = conv.get_next_warmup_date()
        except Exception as e:
            await send_dev_telegram_log(f'[smart_warm_up]\nОшибка get_next_warmup_date\nconv_id={conv_id}\nERROR: {e}',
                                        'ERROR')
            return ConversationResult(
                conv_id=conv_id,
                status='error',
                message=f'Ошибка get_next_warmup_date: {e}'
            )

        if next_warmup_date and now < next_warmup_date:
            return ConversationResult(
                conv_id=conv_id,
                status='skipped',
                message='Еще не прошло достаточное количество времени для следующей рассылки'
            )

        # если мы сюда дошли - значит все механические проверки пройдены, можно анализировать диалог
        analyze_resp = await analyze_conversation(conv_id)

        should_send = analyze_resp.should_send
        should_complete = analyze_resp.should_complete
        next_meeting_datetime = analyze_resp.next_meeting_datetime

        if next_meeting_datetime:
            if next_meeting_datetime:
                if now <= next_meeting_datetime + timedelta(days=2):
                    # Обновляем дату встречи/звонка
                    conv.next_meeting_datetime = next_meeting_datetime
                    return ConversationResult(
                        conv_id=conv_id,
                        status='wait_date',
                        message='У клиента назначена встреча с МОПом (из анализа диалога)'
                    )

        if should_send:
            await cw.send_warmup_message(conversation_id=conv_id)
            # Отправляем прогревающее сообщение
            warmup_number = (conv.warmup_number or 0) + 1
            conv.warmup_number = warmup_number
            conv.last_warmup_date = now
            await cw.send_message(conv_id,f'!!!Отправлено прогревающее собщеение из рассылки {warmup_number}!!!',private=True)
            return ConversationResult(
                conv_id=conv_id,
                status='sent',
                message=f'Отправлено прогревающее сообщение. Рассылка {warmup_number}',
                warmup_number=warmup_number
            )

        elif should_complete:
            # Завершаем диалог
            await cw.close_conversation(conv_id)
            await send_dev_telegram_log(f'[process_conversation]\nЗавершили диалог conv_id={conv_id}]', 'WARMUP')
            return ConversationResult(
                conv_id=conv_id,
                status='completed',
                message=f'Останавливаем коммуникацию с клиентом. Завершаем диалог: {conv_id}'
            )
        else:
            return ConversationResult(
                conv_id=conv_id,
                status='unexpected',
                message='Странный исход. Такого быть не должно!'
            )


    except Exception as e:
        await send_dev_telegram_log(f'[process_conversation]\nКритическая ошибка!\nconv_id={conv_id}\nERROR: {e}','ERROR')
        return ConversationResult(
            conv_id=conv_id,
            status='error',
            message=f'Критическая ошибка в работе функции: {e}'
        )


async def smart_warm_up(session: AsyncSession) -> None:
    try:
        print('стартанули')
        async with session.begin():
            active_inboxes = await TransportActivation.get_active_inboxes(session)
        warmup_inboxes = set(active_inboxes) - ignored_inboxes

        stats = SmartWarmupStats()

        async with ChatwootClient() as cw:
            for inbox_id in warmup_inboxes:
                print(f'обрабатываем инбокс {inbox_id}')
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
                    print(f'обрабатываем диалог {conv_id}')
                    async with session.begin():
                        result = await process_conversation(session, cw, conv_id, portal, status_to_semantic)

                    stats.register(inbox_id=inbox_id, result=result)

        summary = stats.format_summary()
        await send_dev_telegram_log(summary, 'WARMUPINFO')

    except Exception as e:
        tb = traceback.format_exc()
        await send_dev_telegram_log(f'[smart_warm_up]\nКритическая ошибка в кроне!\n\n{tb}')
