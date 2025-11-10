import contextlib
import os
import tempfile
import traceback
from pathlib import Path

import aiohttp
from aiohttp import web

from bx24.bx_utils.parse_call_info import _extract_transcription_text
from chatwoot_api.functions.safe_send_to_chatwoot import safe_send_to_chatwoot
from db.models.transport_activation import TransportActivation
from green_api.download_url import greenapi_download_url
from green_api.functions.get_instance_settings import get_instance_phone
from openai_agents.functions.analyze_document import analyze_document
from openai_agents.functions.analyze_image import analyze_image
from openai_agents.transcribation_client import TranscribeClient
from telegram.send_log import send_dev_telegram_log
from utils.download_to_temp_file import download_to_temp
from utils.ffmpeg_convert_to_wav import convert_to_wav_via_imageio_ffmpeg
from utils.normalize_phone import normalize_phone
from settings import INBOX_TO_TRANSPORT


async def inbound_green_api(request, agent_code, inbox_id):
    """
    Обработчик входящих уведомлений от GREEN API
    Транспортирует в Chatwoot
    """
    try:
        data = await request.json()
        wa_config = INBOX_TO_TRANSPORT.get(inbox_id)
        cw_config = wa_config.chatwoot

        type_webhook = data.get("typeWebhook")
        # Cмена статуса инстанса
        if type_webhook == "stateInstanceChanged":
            state_instance = data.get("stateInstance")
            phone = await get_instance_phone(wa_config)
            if state_instance == 'notAuthorized':
                session_maker = request.app["db_sessionmaker"]
                async with session_maker() as session:
                    await TransportActivation.deactivate(session, inbox_id)
                await send_dev_telegram_log(f"[inbound_green_api]\n\nИнстанс разлогинился!\n@pivograd\n@kateradzivil\n@Im_Artem\n\nномер телефона: {phone}\ninbox_id={inbox_id}\nсостояние инстанса={state_instance} → is_active=False","STATUS", )
                return web.json_response({"status": "ok"})
            elif state_instance == 'authorized':
                session_maker = request.app["db_sessionmaker"]
                async with session_maker() as session:
                    await TransportActivation.activate(session, inbox_id)
                await send_dev_telegram_log(f"[inbound_green_api]\n\nАвторизовали инстанс!\n\nномер телефона: {phone}\ninbox_id={inbox_id}: состояние инстанса={state_instance} → is_active=True","STATUS", )
                return web.json_response({"status": "ok"})
            elif state_instance == 'blocked':
                session_maker = request.app["db_sessionmaker"]
                async with session_maker() as session:
                    await TransportActivation.deactivate(session, inbox_id)
                await send_dev_telegram_log(f"[inbound_green_api]\n\nИнстанс заблокирован!\n@pivograd\n@kateradzivil\n@Im_Artem\n\nномер телефона: {phone}\ninbox_id={inbox_id}: состояние инстанса={state_instance} → is_active=False","STATUS", )
                return web.json_response({"status": "ok"})

        elif type_webhook == "incomingCall":
            if data.get("status") != "offer":
                return web.json_response({"status": "ok"})
            phone = data.get("from", {}).replace("@c.us", "")
            phone = normalize_phone(phone)
            await safe_send_to_chatwoot(phone, str(phone), '', cw_config, comment='[Входящий звонок!]', message_type=0)
            return web.json_response({"status": "ok"})

        # elif type_webhook == "incomingBlock":
        #     ...

        elif not type_webhook == "incomingMessageReceived":
            return web.json_response({"status": "ok"})

        sender_data = data.get("senderData", {})
        name = sender_data.get("senderName", "WhatsApp")
        message_data = data.get("messageData", {})
        chat_id = sender_data.get("chatId", "")

        phone = sender_data.get("sender", "").replace("@c.us", "")
        phone = normalize_phone(phone)
        if not phone:
            return web.json_response({"status": "ok"})

        message_type = message_data.get("typeMessage")
        # 1. Обычное текстовое сообщение
        if message_type == "textMessage":
            text_message = message_data.get("textMessageData", {}).get("textMessage", "")
            if text_message:
                await safe_send_to_chatwoot(phone, name, text_message, cw_config, message_type=0)

        # 2. Расширенное текстовое сообщение
        elif message_type == "extendedTextMessage":
            ext_data = message_data.get("extendedTextMessageData", {})
            message = ext_data.get("text", "")
            if message:
                await safe_send_to_chatwoot(phone, name, message, cw_config, message_type=0)

        # 3. Ответ на сообщение (цитирование)
        elif message_type == "quotedMessage":
            quoted_data = message_data.get("extendedTextMessageData", {})
            quoted_message = message_data.get("quotedMessage", {})
            reply_text = quoted_data.get("text", "")
            original_text = quoted_message.get("textMessage", "")
            full_message = f"Ответ на сообщение:\n«{original_text}»\n\n{reply_text}"
            if reply_text:
                await safe_send_to_chatwoot(phone, name, full_message, cw_config, message_type=0)

        # 4a. Картинки/видео/документы
        elif message_type in ["videoMessage"]:
            file_data = message_data.get("fileMessageData", {})
            message_id = data.get("idMessage")
            async with aiohttp.ClientSession() as session:
                res = await greenapi_download_url(session, wa_config, chat_id, message_id)
                if not res:
                    return web.json_response({"status": "ok"})
                download_url, file_name = res

            full_message = f"{download_url}"
            await safe_send_to_chatwoot(phone, name, full_message, cw_config, message_type=0)

        # 4b. Картинка/изображение
        elif message_type == "imageMessage":
            message_id = data.get("idMessage")
            async with aiohttp.ClientSession() as session:
                res = await greenapi_download_url(session, wa_config, chat_id, message_id)
                if not res:
                    return web.json_response({"status": "ok"})
                download_url, file_name = res
            image_summary = await analyze_image(download_url)
            image_msg = f'[Summary прикрепленной картинки]:\n\n{image_summary}'
            caption = message_data.get("fileMessageData", {}).get("caption")
            full_message = f'[СООБЩЕНИЕ С ИЗОБРАЖЕНИЕМ]\n\nТекст сообщения:\n{caption}\nСсылка на изображение: {download_url}\n\n{image_msg}'
            await safe_send_to_chatwoot(phone, name, full_message, cw_config, message_type=0)
            return web.json_response({"status": "ok"})

        # 4c. Аудиосообщение
        elif message_type == "audioMessage":
            message_id = data.get("idMessage")
            async with aiohttp.ClientSession() as session:
                res = await greenapi_download_url(session, wa_config, chat_id, message_id)
                if not res:
                    await send_dev_telegram_log(f"[inbound_green_api.audioMessage]\nНе удалось получить downloadUrl\nmessage_id: {message_id}", 'WARNING')
                    return web.json_response({"status": "ok"})
                download_url, file_name = res

                tmp_path = None
                try:
                    tmp_path = await download_to_temp(session, download_url, file_name)
                    wav_path = Path(tempfile.gettempdir()) / (Path(file_name).stem + ".wav")
                    await convert_to_wav_via_imageio_ffmpeg(tmp_path, str(wav_path))

                    transcript = await TranscribeClient().transcribe(audio_file_path=str(wav_path))
                    text = _extract_transcription_text(transcript)
                    if text and text.strip():
                        header = "🎤 Голосовое сообщение"
                        full_message = f"{header}:\nСсылка на файл c аудио: {download_url}\n\n[Транскрибация]:\n{text.strip()}"
                        await safe_send_to_chatwoot(phone, name, full_message, cw_config, message_type=0)
                    else:
                        fallback_msg = f"{file_name}: {download_url}"
                        await safe_send_to_chatwoot(phone, name, fallback_msg, cw_config, message_type=0)

                except Exception as e:
                    await send_dev_telegram_log(
                        f"[inbound_green_api.audioMessage]\nОшибка транскрибации: {e}", 'WARNING')
                    fallback_msg = f"{file_name}: {download_url}"
                    await safe_send_to_chatwoot(phone, name, fallback_msg, cw_config, message_type=0)
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        with contextlib.suppress(Exception):
                            os.remove(tmp_path)

                    if wav_path and os.path.exists(wav_path):
                        with contextlib.suppress(Exception):
                            os.remove(wav_path)

        # 4d. Сообщение с документом
        elif message_type == "documentMessage":
            message_id = data.get("idMessage")
            async with aiohttp.ClientSession() as session:
                res = await greenapi_download_url(session, wa_config, chat_id, message_id)
                if not res:
                    return web.json_response({"status": "ok"})
                download_url, file_name = res
            document_summary = await analyze_document(download_url)
            document_msg = f'[Summary прикрепленного документа]:\n\n{document_summary}'
            caption = message_data.get("caption")
            full_message = f'[СООБЩЕНИЕ С ДОКУМЕНТОМ]\n\nТекст сообщения:\n{caption}\nСсылка на документ: {download_url}\n\n{document_msg}'
            await safe_send_to_chatwoot(phone, name, full_message, cw_config, message_type=0)
            return web.json_response({"status": "ok"})

        # 5. Контакт
        elif message_type == "contactMessage":
            contact_data = message_data.get("contactMessageData", {})
            contact_name = contact_data.get("displayName", "Контакт")
            vcard = contact_data.get("vcard", "")
            full_message = f"📇 Получен контакт:\n{contact_name}\n{vcard}"
            await safe_send_to_chatwoot(phone, name, full_message, cw_config, message_type=0)

        # 6. Геолокация
        elif message_type == "locationMessage":
            location_data = message_data.get("locationMessageData", {})
            latitude = location_data.get("latitude")
            longitude = location_data.get("longitude")
            address = location_data.get("address", "")
            full_message = f"📍 Геолокация:\nАдрес: {address}\nКоординаты: {latitude}, {longitude}"
            await safe_send_to_chatwoot(phone, name, full_message, cw_config, message_type=0)

        # 7. Стикер
        elif message_type == "stickerMessage":
            sticker_data = message_data.get("stickerMessageData", {})
            emoji = sticker_data.get("emoji", "")
            full_message = f"🟩 Стикер: {emoji or 'Получен стикер'}"
            await safe_send_to_chatwoot(phone, name, full_message, cw_config, message_type=0)

        # 8. Опрос
        elif message_type == "pollMessage":
            poll_data = message_data.get("pollMessageData", {})
            question = poll_data.get("name", "Опрос")
            options = poll_data.get("options", [])
            options_text = ", ".join(opt.get("name", "") for opt in options)
            full_message = f"📝 Опрос: {question}\nВарианты: {options_text}"
            await safe_send_to_chatwoot(phone, name, full_message, cw_config, message_type=0)

        return web.json_response({"status": "ok"})
    except Exception as e:
        tb = traceback.format_exc()
        await send_dev_telegram_log(
            f'[inbound_green_api]\nКритическая ошибка при обработке уведомления WA\nTRACEBACK: {tb}', 'ERROR')
        return web.json_response({"status": "error"})
