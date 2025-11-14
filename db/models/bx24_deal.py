from __future__ import annotations

import traceback
from typing import Optional, Dict, Any, ClassVar
from datetime import datetime, timezone, timedelta

from aiohttp import web
from sqlalchemy import Integer, String, DateTime, UniqueConstraint, select, or_, and_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from bx24.bx_utils.parse_call_info import parse_call_info
from chatwoot_api.chatwoot_client import ChatwootClient
from db.models.base import Base

from bx24.bx_utils.bitrix_token import BitrixToken
from db.models.bx_deal_cw_link import link_deal_with_conversation, get_conversation_ids_for_deal, BxDealCwLink
from settings import but_map_dict, PORTAL_AGENTS
from telegram.send_log import send_dev_telegram_log
from utils.normalize_phone import normalize_phone


class Bx24Deal(Base):
    __tablename__ = "bx_deal"
    __table_args__ = (UniqueConstraint("bx_id", "bx_portal", name="uq_bx_deals_bx_id_portal"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    bx_id: Mapped[int] = mapped_column(Integer, nullable=False)
    bx_portal: Mapped[str] = mapped_column(String(255), nullable=False)
    bx_funnel_id: Mapped[str] = mapped_column(String(55), nullable=False)
    bx_contact_id: Mapped[int] = mapped_column(Integer, nullable=True)

    last_sync_chatwoot: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    last_transcribed_call: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True,default=None)
    last_sync_comment_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=None)

    stage_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    _session_maker: ClassVar[Optional[async_sessionmaker[AsyncSession]]] = None

    @classmethod
    def configure_sessionmaker(cls, sm: async_sessionmaker[AsyncSession]) -> None:
        cls._session_maker = sm

    @classmethod
    def _ensure_sessionmaker(cls) -> None:
        if cls._session_maker is None:
            raise RuntimeError(
                "Bx24Deal._session_maker не сконфигурирован. "
                "Вызови Bx24Deal.configure_sessionmaker(...) при старте приложения."
            )

    @property
    def but(self) -> BitrixToken:
        return but_map_dict.get(self.bx_portal)

    @property
    def unique_code(self) -> str:
        return f'{self.bx_portal}.{self.bx_id}'

    async def get_bx_data(self, bx_):
        ...

    async def get_timeline_comments(self):
        """
        Получаем комментарии к сделке из Bitrix24.
        """
        #TODO сделать call_list (у обычного call_api
        response = self.but.call_api_method(
            'crm.timeline.comment.list',
            {
                'filter': {
                    'ENTITY_ID': self.bx_id,
                    'ENTITY_TYPE': 'deal',
                },
                'select': ['ID', 'CREATED', 'COMMENT']
            }
        )

        return response.get('result', [])


    async def get_calls_since(self):
        """
        Получает звонки из timeline сделки Bitrix24.
        """
        filter_ = {'OWNER_TYPE_ID': 2, 'OWNER_ID': self.bx_id, 'PROVIDER_TYPE_ID': "CALL"}

        if self.last_transcribed_call:
            since_utc = self.last_transcribed_call.astimezone(timezone.utc)
            since_utc = since_utc + timedelta(seconds=1)
            filter_[">START_TIME"] = since_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

        response = self.but.call_api_method(
            'crm.activity.list',
            {
                'filter': filter_,
                'select': ['*'],
                'order': {'START_TIME': 'ASC'},
            }
        )
        return response.get('result', [])

    async def handle_new_call(self, call: dict[str, Any]):
        """
        Обработчик нового звонка в сделке
        """
        try:
            info = parse_call_info(call)
            result: Dict[str, Any] = {
                "call_id": info.id,
                "subject": info.subject,
                "direction": info.direction,
                "status": info.status,
                "start": info.start.isoformat() if info.start else None,
                "end": info.end.isoformat() if info.end else None,
                "duration": info.duration_human,
                "transcribation": None,
                "stt": None,
                "error": None,
            }

            if not info.file_id:
                await send_dev_telegram_log(f"[handle_new_call]\nНет file_id для call_id={info.id}")
                return result

            file_url = self.but.call_api_method('disk.file.get', {'id': info.file_id}).get('result', {}).get(
                'DOWNLOAD_URL')
            if not file_url:
                await send_dev_telegram_log(
                    f"[handle_new_call]\nНе удалось получить DOWNLOAD_URL для file_id={info.file_id}, portal={self.bx_portal}")
                return result

            tmp_path = ''
            try:
                import os, tempfile, aiohttp, aiofiles
                fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
                os.close(fd)

                async with aiohttp.ClientSession() as session:
                    async with session.get(file_url) as resp:
                        if resp.status != 200:
                            result["error"] = f"Ошибка загрузки файла: {resp.status}"
                            return result

                        async with aiofiles.open(tmp_path, "wb") as f:
                            async for chunk in resp.content.iter_chunked(1024 * 64):
                                await f.write(chunk)
                            await f.flush()

                size = os.path.getsize(tmp_path)
                if size == 0:
                    result["error"] = "Файл записи пустой (0 байт)"
                    await send_dev_telegram_log(f"[handle_new_call]\nФайл пустой, call_id={info.id}")
                    return result

                from openai_agents.transcribation_client import TranscribeClient
                transcribation = await TranscribeClient().transcribe(tmp_path)

                result['transcribation'] = transcribation.text
                return result

            except Exception as e:
                result["error"] = f"Ошибка скачивания/транскрибации: {str(e)}"
                await send_dev_telegram_log(f"[handle_new_call]\nОшибка при скачивании/транскрибации файла: {str(e)}")
                return result

            finally:
                import os
                try:
                    if tmp_path:
                        os.remove(tmp_path)
                except Exception as e:
                    await send_dev_telegram_log(f'[handle_new_call]\nОшибка при удалении временного файла(очистке): {e}')

        except Exception as e:
            await send_dev_telegram_log(f"[handle_new_call]\nОшибка при обработке звонка: {str(e)}\nCALL: {call}")
            return {'error': str(e)}

    async def init_chatwoot(self, session: AsyncSession) -> tuple[bool, list[Optional[int]], Optional[int]]:
        """
        Инициализация связки с Chatwoot.
        """
        false_response = (False, [], None)
        try:
            persistent: Bx24Deal = await session.merge(self, load=True)

            if not persistent.bx_contact_id:
                await send_dev_telegram_log(f'[init_chatwoot]\nУ сделки нет контакта!\nbx portal: {persistent.bx_portal}'
                                            f'\nbx deal id: {persistent.bx_id}', "WARNING")
                return false_response

            bx_contact = persistent.but.call_api_method('crm.contact.get', {'id': persistent.bx_contact_id}).get('result')
            phone = bx_contact.get('PHONE', [{}])
            phone = normalize_phone(phone[0].get('VALUE'))
            if not phone:
                await send_dev_telegram_log(
                    f"[init_chatwoot]\nНевалидный номер у контакта!\nbx contact id: {persistent.bx_contact_id}\nphone: {phone}\n"
                    f"ID сделки: {persistent.bx_id}\nПортал: {persistent.bx_portal}", "WARNING"
                )
                return false_response

            identifier = phone.lstrip("+")
            conversation_ids = []
            async with ChatwootClient() as cw:
                chatwoot_contact_id = await cw.get_contact_id(identifier=identifier)
                if not chatwoot_contact_id:
                    await send_dev_telegram_log(f'[init_chatwoot]\nНе найден контакт в CW с identifier: {identifier}', "INFO")
                    return false_response

                inboxes_id = await cw.get_conversation_inboxes(chatwoot_contact_id)

                for inbox_id in inboxes_id:
                    conv_id = await cw.get_conversation_id(contact_id=chatwoot_contact_id, inbox_id=inbox_id)
                    if not conv_id:
                        await send_dev_telegram_log(f'[init_chatwoot]\nНе нашли диалог в CW для:\ncw_contact_id: {chatwoot_contact_id}\ninbox_id: {inbox_id}', "DEV")
                        continue
                    if not await cw.is_active_conversation(conv_id):
                        continue
                    await cw.set_bx24_deal_link(conv_id,f'https://{self.bx_portal}/crm/deal/details/{self.bx_id}/')
                    await link_deal_with_conversation(
                        session=session,
                        bx_portal=persistent.bx_portal,
                        bx_deal_id=persistent.bx_id,
                        cw_conversation_id=conv_id,
                        cw_inbox_id=inbox_id,
                        cw_contact_id=chatwoot_contact_id,
                    )
                    conversation_ids.append(conv_id)
                    await send_dev_telegram_log(f'Связан диалог CW со сделкой в BX24\n\n'
                                                f'ID диалога CW: {conv_id}\nID контакта CW: {chatwoot_contact_id}\n'
                                                f'Портал BX24: {self.bx_portal}\nID сделки BX24: {self.bx_id}\n', 'INFO')

            return True, conversation_ids, chatwoot_contact_id

        except Exception as e:
            await send_dev_telegram_log(f'[init_chatwoot]\nКритическая ошибка!\nerror: {e}')
            return false_response

    @staticmethod
    async def get_or_create(session: AsyncSession, deal_id, domain):
        stmt = select(Bx24Deal).where(
            Bx24Deal.bx_id == deal_id,
            Bx24Deal.bx_portal == domain,
        )
        obj = await session.scalar(stmt)
        if obj:
            return obj

        but = but_map_dict[domain]
        bx_deal = but.call_api_method('crm.deal.get', {'id': deal_id})['result']

        async with session.begin_nested():
            obj = Bx24Deal(
                bx_id=deal_id,
                bx_portal=domain,
                bx_funnel_id=str(bx_deal.get('CATEGORY_ID')),
                bx_contact_id=int(bx_deal.get('CONTACT_ID')),
                stage_id=bx_deal.get('STAGE_ID'),
            )
            session.add(obj)
            try:
                await session.flush()
            except IntegrityError as e:
                tb = traceback.format_exc()
                await send_dev_telegram_log(f'[Bx24Deal.get_or_create]\nОшибка!\n{tb}', 'ERROR')

        return await session.scalar(stmt)

    async def save_max_last_transcribed_call(self, session: AsyncSession, latest_call_dt: datetime) -> None:
        """
        Меняет last_transcribed_call ТОЛЬКО если новое значение больше.
        """
        try:
            if latest_call_dt is None:
                return
            await session.execute(
                update(Bx24Deal)
                .where(and_(
                    Bx24Deal.bx_id == self.bx_id,
                    Bx24Deal.bx_portal == self.bx_portal,
                    or_(Bx24Deal.last_transcribed_call.is_(None),
                        Bx24Deal.last_transcribed_call < latest_call_dt)
                ))
                .values(last_transcribed_call=latest_call_dt)
            )
        except Exception as e:
            await send_dev_telegram_log(f'[save_max_last_transcribed_call]\nОшибка при сохранении даты последнего транскрибированного звонка: {e}')
            raise e

    async def save_max_last_sync_comment_id(self, session: AsyncSession, max_comment_id: int) -> None:
        """
        Меняет last_sync_comment_id только если новое значение больше.
        """
        try:
            if max_comment_id is None:
                return
            await session.execute(
                update(Bx24Deal)
                .where(and_(
                    Bx24Deal.bx_id == self.bx_id,
                    Bx24Deal.bx_portal == self.bx_portal,
                    or_(Bx24Deal.last_sync_comment_id.is_(None),
                        Bx24Deal.last_sync_comment_id < max_comment_id)
                ))
                .values(last_sync_comment_id=max_comment_id)
            )
        except Exception as e:
            await send_dev_telegram_log(f'[save_max_last_sync_comment_id]\nОшибка при сохранении id посленднего синхронизированного коммента: {e}', 'ERROR')
            raise e

    async def sync_deal_stage_to_chatwoot(self, session: AsyncSession) -> bool:
        """
        Отслеживает изменения стадии сделки в BX24
        Сохраняет актуальную стадию в БД, и транслирует информацию в приватные комментарии диалога Chatwoot
        """
        try:
            persistent: Bx24Deal = await session.merge(self, load=True)

            bx_deal = persistent.but.call_api_method('crm.deal.get', {'id': persistent.bx_id}).get('result')
            if not bx_deal:
                await send_dev_telegram_log(
                    f"[sync_deal_stage_to_chatwoot]\nНе удалось получить сделку.\n"
                    f"Портал: {persistent.bx_portal}\nСделка: {persistent.bx_id}", 'WARNING'
                )
                return False
            funnel_changed = False
            new_funnel_raw = bx_deal.get('CATEGORY_ID')
            if new_funnel_raw:
                new_funnel_id = str(new_funnel_raw)
                old_funnel_id = persistent.bx_funnel_id
                if new_funnel_id != old_funnel_id:
                    persistent.bx_funnel_id = new_funnel_id
                    funnel_changed = True

            new_stage_id: Optional[str] = bx_deal.get('STAGE_ID')
            if not new_stage_id:
                await send_dev_telegram_log(
                    f"[sync_deal_stage_to_chatwoot]\nНе удалось получить STAGE_ID.\n"
                    f"Портал: {persistent.bx_portal}\nСделка: {persistent.bx_id}\nbx_deal: {bx_deal}", "WARNING"
                )
                return False

            old_stage_id = persistent.stage_id

            if new_stage_id == old_stage_id:
                if funnel_changed:
                    await session.flush()
                return True

            persistent.stage_id = new_stage_id

            conversation_ids = await get_conversation_ids_for_deal(session, bx_portal=persistent.bx_portal, bx_id=persistent.bx_id)

            if not conversation_ids:
                await send_dev_telegram_log('[sync_deal_stage_to_chatwoot]\nПопытка синхронизации сделки без связи с CW\nСюда такое не должно попадать!!', 'ERROR')
                return False

            if old_stage_id is None:
                await session.flush()
                return True

            def _stage_name(status_id: str) -> str:
                try:
                    res = persistent.but.call_api_method(
                        'crm.status.list',
                        {'filter': {'STATUS_ID': status_id}}
                    ).get('result', [])
                    return (res[0].get('NAME') if res else None) or status_id
                except Exception:
                    return status_id

            old_stage_name = _stage_name(old_stage_id)
            new_stage_name = _stage_name(new_stage_id)

            msg = f'[смена стадии сделки BX24]\n\n{old_stage_name} → {new_stage_name}'

            try:
                async with ChatwootClient() as cw:
                    for conversation_id in conversation_ids:
                        await cw.send_message(conversation_id, msg, private=True)
                return True
            except Exception as e:
                await send_dev_telegram_log(
                    f"[sync_deal_stage_to_chatwoot]\nОшибка отправки заметки в Chatwoot: {e}\n"
                    f"Портал: {persistent.bx_portal}\nСделка: {persistent.bx_id}", 'ERROR'
                )
                return False
            finally:
                await session.flush()


        except Exception as e:
            await send_dev_telegram_log(
                f"[sync_deal_stage_to_chatwoot]\nКритическая ошибка при смене стадии: {e}\n"
                f"Портал: {self.bx_portal}\nСделка: {self.bx_id}", 'ERROR'
            )
            return False

    @classmethod
    async def notify_responsible_by_conversation(cls, conversation_id: int, marker: str):
        """
        Открывает read-only сессию, читает сделки по conversation_id и отправляет уведомления в Bitrix.
        """

        cls._ensure_sessionmaker()
        try:
            async with cls._session_maker() as session:
                stmt = (
                    select(cls)
                    .join(
                        BxDealCwLink,
                        and_(
                            BxDealCwLink.bx_portal == cls.bx_portal,
                            BxDealCwLink.bx_deal_id == cls.bx_id,
                        ),
                    )
                    .where(BxDealCwLink.cw_conversation_id == int(conversation_id))
                )
                result = await session.execute(stmt)
                deals: list[Bx24Deal] = result.unique().scalars().all()

                if not deals:
                    await send_dev_telegram_log(
                        f"[notify_responsible_by_conversation]\n"
                        f"Сделка не найдена для conversation_id={conversation_id}\n"
                        f"некуда отправить уведомление!",
                        "MANAGERS",
                    )
                    return False

                for deal in deals:
                    deal_bx_data = deal.but.call_api_method('crm.deal.get', {'id': deal.bx_id}).get('result')
                    if not deal_bx_data or deal_bx_data.get('CLOSED') == 'Y':
                        continue

                    assigned_id = deal_bx_data.get('ASSIGNED_BY_ID')
                    if not assigned_id:
                        await send_dev_telegram_log(
                            f"[notify_responsible_by_conversation]\nНет ответственного в сделке bx_id: {deal.bx_id}\nconversation_id={conversation_id}\nнекому отправить уведомление!", 'MANAGERS')
                        continue
                    # ID bx user МОЙ, Кати и Артёма Костецкого + ответственный за сделку
                    users_id = [182, 6784, 6014, int(assigned_id)]

                    # Получаем/создаём чат по сделке в BX24
                    bx_chat_resp = deal.but.call_api_method('im.chat.get', {'ENTITY_TYPE': 'CRM', 'ENTITY_ID': f'DEAL|{deal.bx_id}'}).get('result')
                    bx_chat_id = bx_chat_resp.get('ID') if bx_chat_resp else None
                    if not bx_chat_id:
                        bx_chat_id = deal.but.call_api_method('im.chat.add', {
                            'TITLE': f'СДЕЛКА: {deal_bx_data.get("TITLE", "Не удалось получить название сделки.")}',
                            'USERS': users_id,
                            'ENTITY_TYPE': 'CRM',
                            'ENTITY_ID': f'DEAL|{deal.bx_id}'
                        }).get('result')

                    message = f'Обратите внимание на переписку Агента с клиентом в mbk-chat!\nОбнаруженно слово: {marker}\nID диалога в CW: {conversation_id}'
                    deal.but.call_api_method('im.message.add',{'DIALOG_ID': f'chat{bx_chat_id}', 'MESSAGE': message}).get('result')
                    # TODO: выставить в сделке поле был призыва менеджера в True

                return True

        except Exception as e:
            tb = traceback.format_exc()
            await send_dev_telegram_log(f'[notify_responsible_by_conversation]\nconversation_id: {conversation_id}\nОшибка при отправке уведомления в Битркис: {tb}', 'ERROR')
            return False


    async def sync_deal_timeline_comments_to_chatwoot(self, session: AsyncSession):
        """
        Cинхронизирует комменты из таймлайна сделки с приватными комментариями чата в chatwoot
        """
        comments = await self.get_timeline_comments()
        comments.sort(key=lambda c: int(c["ID"]))

        last_id = self.last_sync_comment_id or 0
        new_comments = [c for c in comments if int(c["ID"]) > last_id]
        if not new_comments:
            return web.Response(text="OK", status=200)

        conversation_ids = await get_conversation_ids_for_deal(session, bx_portal=self.bx_portal, bx_id=self.bx_id)
        if not conversation_ids:
            await send_dev_telegram_log(
                '[sync_deal_timeline_comments_to_chatwoot]\nПопытка синхронизации сделки без связи с CW\nСюда такое не должно попадать!!',
                'ERROR')
            return False

        async with ChatwootClient() as cw:
            for c in new_comments:
                comment_text = c.get('COMMENT')
                for conversation_id in conversation_ids:
                    await cw.send_message(
                        conversation_id,
                        f'Комментарий из сделки BX24:\n {comment_text}',
                        private=True
                    )

        max_id = int(new_comments[-1]["ID"])

        await self.save_max_last_sync_comment_id(session, max_id)

        return True