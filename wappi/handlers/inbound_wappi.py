import tempfile
import traceback
from pathlib import Path

import aiohttp
from aiohttp import web

from chatwoot_api.chatwoot_client import ChatwootClient
from openai_agents.functions.analyze_document import analyze_document
from settings import INBOX_TO_TRANSPORT
from openai_agents.functions.analyze_image import analyze_image
from bx24.bx_utils.parse_call_info import _extract_transcription_text
from openai_agents.transcribation_client import TranscribeClient
from telegram.send_log import send_dev_telegram_log
from utils.download_to_temp_file import download_to_temp
from utils.ffmpeg_convert_to_wav import convert_to_wav_via_imageio_ffmpeg
from utils.normalize_phone import normalize_phone
from wappi.wappi_client import WappiClient


async def inbound_wappi(request, agent_code, inbox_id):
    """
    Обработчик входящих уведомлений от WAPPI Telegram API
    Транспортирует в Chatwoot
    """
    try:
        data = await request.json()
        await send_dev_telegram_log(f'[inbound_wappi]\n\n {data}', 'DEV')
        messages = data.get("messages")

        if not messages or not isinstance(messages, list):
            return web.Response(text="SKIP", status=200)

        message_data = messages[0]
        if not message_data.get("wh_type") == 'incoming_message':
            return web.Response(text="OK", status=200)

        message_text = message_data.get("body")
        contact_indentifier = message_data.get("from")
        if not contact_indentifier:
            # скип
            return web.Response(text="SKIP, не удалось определить контакт", status=200)

        if message_data.get('type') == 'image':
            download_url = message_data.get('file_link')
            image_summary = await analyze_image(base64_image=message_text)
            image_msg = f'[Summary прикрепленной картинки]:\n\n{image_summary}'
            caption = message_data.get("caption")
            message_text = f'[СООБЩЕНИЕ С ИЗОБРАЖЕНИЕМ]\n\nТекст сообщения:\n{caption}\nСсылка на изображение: {download_url}\n\n{image_msg}'
        elif message_data.get('type') == 'ptt':
            async with aiohttp.ClientSession() as session:
                download_url = message_data.get('file_link')
                tmp_path = await download_to_temp(session, download_url, 'somefile.mp3')
                wav_path = Path(tempfile.gettempdir()) / (Path('somefile').stem + ".wav")
                await convert_to_wav_via_imageio_ffmpeg(tmp_path, str(wav_path))
                transcript = await TranscribeClient().transcribe(wav_path)
                audio_text = _extract_transcription_text(transcript)
                if audio_text and audio_text.strip():
                    header = "🎤 Голосовое сообщение"
                    message_text = f"{header}:\nСсылка на файл c аудио: {download_url}\n\n[Транскрибация]:\n{audio_text.strip()}"
        elif message_data.get('type') == 'document':
            download_url = message_data.get('file_link')
            document_summary = await analyze_document(download_url)
            document_msg = f'[Summary прикрепленного документа]:\n\n{document_summary}'
            caption = message_data.get("caption")
            message_text = f'[СООБЩЕНИЕ С ДОКУМЕНТОМ]\n\nТекст сообщения:\n{caption}\nСсылка на документ: {download_url}\n\n{document_msg}'


        tg_config = INBOX_TO_TRANSPORT[inbox_id]
        wappi_instance_id, wappi_token = tg_config.get_waapi_params()

        async with WappiClient(wappi_token, wappi_instance_id) as client:
            contact = await client.get_contact(contact_indentifier)
            if not contact:
                await send_dev_telegram_log(f'[inbound_wappi]\nНет контакта в TG: {contact_indentifier}', 'WARNING')
                return web.Response(text="SKIP нет контакта в TG", status=200)

            phone = contact.get('number')
            if not phone:
                await send_dev_telegram_log(f'[inbound_wappi]\nНет телефона у контакта в TG: {contact_indentifier}', 'WARNING')
                return web.Response(text="SKIP нет телефона у контакта в TG", status=200)

        phone = normalize_phone(phone)
        identifier = phone.lstrip("+")

        async with ChatwootClient() as cw_client:
            cw_contact_id = await cw_client.get_contact_id(identifier)
            if not cw_contact_id:
                await send_dev_telegram_log(f'[inbound_wappi]\nНе найден контакт в CW!\nidentifier: {identifier}',
                                            'WARNING')
                return web.Response(text="SKIP Не найден контакт в CW", status=200)
            cw_conversation_id = await cw_client.get_conversation_id(cw_contact_id, inbox_id)
            if not cw_conversation_id:
                await send_dev_telegram_log(f'[inbound_wappi]\nНе найден диалог в CW!\ncontact_identifier: {identifier}\ninbox_id: {inbox_id}',
                                            'WARNING')
                return web.Response(text="SKIP Не найден диалог в CW!", status=200)
            await cw_client.send_message(cw_conversation_id, message_text, message_type=0)
            return web.Response(text="OK", status=200)


    except Exception as e:
        tb = traceback.format_exc()
        await send_dev_telegram_log(f'[inbound_wappi]\nНепредвиденная ошибка: {tb}', 'ERROR')
        return web.Response(text="ERROR", status=200)
