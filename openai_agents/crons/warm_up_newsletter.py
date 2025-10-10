from chatwoot_api.chatwoot_client import ChatwootClient
from openai_agents.functions.analyze_conversation import analyze_conversation
from openai_agents.functions.write_warm_up_message import main_send
from telegram.send_log import send_dev_telegram_log


async def warm_up_newsletter(inbox_id):
    """
    Отправляет прогревающее сообщение в 10 подходящих диалогов.
    """
    try:
        async with ChatwootClient() as cw:
            open_ids = await cw.get_open_conversation_ids(inbox_id=inbox_id)
            ids_count = 0
            for c_id in open_ids:
                if ids_count >= 10:
                    break
                try:
                    if not await cw.is_stopped_communication(c_id):
                        continue
                    analyze_resp = await analyze_conversation(c_id)
                    if analyze_resp.should_send is True:
                        message = await main_send(c_id)
                        await cw.send_message(c_id, message)
                        await cw.send_message(c_id, f'!!!Отправлено прогревающее собщеение из рассылки {analyze_resp.warm_up_number}!!!', private=True)
                        await send_dev_telegram_log(f'[warm_up_newsletter]\nОтправлено прогревающее собщеение!\nID диалога CW: {c_id}\n\nСообщение:\n\n{message}', 'WARMUP')
                        ids_count += 1
                except Exception as e:
                    await send_dev_telegram_log(f'[warm_up_newsletter]\nОшибка при взаимодействии с диалогом!\nID диалога CW: {c_id}\nerror: {e}\n', 'WARNING')

    except Exception as e:
        await send_dev_telegram_log(f'[warm_up_newsletter]\nГлобальная ошибка в работе скрипта!\nID диалога CW: {c_id}\nerror: {e}\n','ERROR')
