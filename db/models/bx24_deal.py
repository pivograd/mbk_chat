from __future__ import annotations

import traceback
from typing import Optional, Dict, Any, ClassVar
from datetime import datetime, timezone, timedelta

from sqlalchemy import Integer, String, DateTime, UniqueConstraint, select, or_, and_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from bx24.bx_utils.parse_call_info import parse_call_info
from chatwoot_api.chatwoot_client import ChatwootClient
from db.models.base import Base

from bx24.bx_utils.bitrix_token import BitrixToken
from openai_agents.transcribation_client import TranscribeClient
from settings import but_map_dict, FV_MBK_DIALOG_BOOL_FIELD, PORTAL_AGENTS
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

    chatwoot_contact_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chatwoot_conversation_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

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

                # await send_dev_telegram_log(f"[handle_new_call]\nОтправка на транскрибацию ({size} байт)")

                transcribation = await TranscribeClient().transcribe(tmp_path)

                # await send_dev_telegram_log(f"[handle_new_call]\nПолучена транскрибация: {transcribation}")
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

    async def init_chatwoot(self, session: AsyncSession) -> tuple[bool, Optional[int], Optional[int]]:
        """
        Инициализация связки с Chatwoot. Работает с ПРИКРЕПЛЁННОЙ копией объекта.
        """
        persistent: Bx24Deal = await session.merge(self, load=True)

        # получаем ID агента chatwoot связанного с воронкой сделок
        inbox_id = PORTAL_AGENTS.get(persistent.bx_portal, {}).get(persistent.bx_funnel_id)

        if not inbox_id:
            return False, None, None

        if not persistent.bx_contact_id:
            return False, None, None

        bx_contact = persistent.but.call_api_method('crm.contact.get', {'id': persistent.bx_contact_id}).get('result')
        phone = bx_contact.get('PHONE')
        if not phone:
            return False, None, None

        phone = normalize_phone(phone[0].get('VALUE'))
        if not phone:
            await send_dev_telegram_log(
                f"[Bx24Deal:init_chatwoot] Невалидный номер у контакта {persistent.bx_contact_id}: {phone}\n"
                f"ID сделки: {persistent.bx_id}\nПортал: {persistent.bx_portal}"
            )
            return False, None, None

        identifier = phone.lstrip("+")
        name = bx_contact.get('NAME') or f'Контакт из BX24 {persistent.bx_portal}'
        async with ChatwootClient() as cw:
            chatwoot_contact_id = await cw.get_contact_id(identifier=identifier)
            if not chatwoot_contact_id:
                # await send_dev_telegram_log(f'[init_chatwoot]\nНе найден контакт с identifier: {identifier}')
                return False, None, None
            conversation_id = await cw.get_conversation_id(contact_id=chatwoot_contact_id, inbox_id=inbox_id)
            if not conversation_id:
                if persistent.chatwoot_contact_id != chatwoot_contact_id:
                    persistent.chatwoot_contact_id = chatwoot_contact_id
                    await session.flush()
                return False, None, None

            is_active_conv = await cw.is_active_conversation(conversation_id)
            if not is_active_conv:
                if persistent.chatwoot_contact_id != chatwoot_contact_id:
                    persistent.chatwoot_contact_id = chatwoot_contact_id
                    await session.flush()
                return False, None, chatwoot_contact_id

            await cw.set_bx24_deal_link(conversation_id, f'https://{self.bx_portal}/crm/deal/details/{self.bx_id}/')

            # Техническое поле-флаг в BX24
            bx_deal = persistent.but.call_api_method('crm.deal.get', {'id': persistent.bx_id}).get('result')
            if bx_deal.get(FV_MBK_DIALOG_BOOL_FIELD) != '1':
                persistent.but.call_api_method(
                    'crm.deal.update',
                    {'id': persistent.bx_id, 'fields': {FV_MBK_DIALOG_BOOL_FIELD: '1'}}
                )
            # Костыльно проверяем и меняем воронку сделки:
            if bx_deal.get('CATEGORY_ID') != persistent.bx_funnel_id:
                persistent.bx_funnel_id = bx_deal.get('CATEGORY_ID')
                await session.flush()
                await send_dev_telegram_log('[init_chatwoot]\nОбновилась воронка у сделки!')

        if (persistent.chatwoot_conversation_id == conversation_id and
                persistent.chatwoot_contact_id == chatwoot_contact_id):
            return True, conversation_id, chatwoot_contact_id

        persistent.chatwoot_conversation_id = conversation_id
        persistent.chatwoot_contact_id = chatwoot_contact_id
        await session.flush()

        await send_dev_telegram_log(f'Связан диалог CW со сделкой в BX24\n\n'
                                    f'ID диалога CW: {conversation_id}\nID контакта CW: {chatwoot_contact_id}\n'
                                    f'Портал BX24: {self.bx_portal}\nID сделки BX24: {self.bx_id}\n')

        return True, conversation_id, chatwoot_contact_id

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
            except IntegrityError:
                pass

        return await session.scalar(stmt)

    @classmethod
    async def get_chatwoot_conversation_id(cls, session: AsyncSession, deal_id: int, portal: str,) -> Optional[int]:
        """
        Вернёт ID диалога Chatwoot связанного со сделкой.
        Если сделки нет или ID отсутствует, вернёт None.
        """
        stmt = (
            select(cls.chatwoot_conversation_id)
            .where(
                cls.bx_id == int(deal_id),
                cls.bx_portal == portal,
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

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
            await send_dev_telegram_log(f'[save_max_last_transcribed_call]\nОшибка при сохранении id посленднего синхронизированного коммента: {e}')
            raise e

    async def sync_deal_stage_to_chatwoot(self, session: AsyncSession) -> bool:
        """
        Отслеживает изменения стадии сделки в BX24
        """
        try:
            persistent: Bx24Deal = await session.merge(self, load=True)

            bx_deal = persistent.but.call_api_method('crm.deal.get', {'id': persistent.bx_id}).get('result')
            if not bx_deal:
                await send_dev_telegram_log(
                    f"[sync_deal_stage_to_chatwoot] Не удалось получить сделку.\n"
                    f"Портал: {persistent.bx_portal}\nСделка: {persistent.bx_id}"
                )
                return False

            new_stage_id: Optional[str] = bx_deal.get('STAGE_ID')
            if not new_stage_id:
                await send_dev_telegram_log(
                    f"[sync_deal_stage_to_chatwoot] Не удалось получить STAGE_ID. "
                    f"Портал: {persistent.bx_portal}, Сделка: {persistent.bx_id}"
                )
                return False

            old_stage_id = persistent.stage_id

            if new_stage_id == old_stage_id:
                return True

            persistent.stage_id = new_stage_id

            # если нет связки
            if not persistent.chatwoot_conversation_id:
                await send_dev_telegram_log('[sync_deal_stage_to_chatwoot]\nПопытка синхронизации стадии сделки без связи с CW')
                return True

            # если это первичная инициализация — не шлём заметку, просто фиксируем
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
                    await cw.send_message(persistent.chatwoot_conversation_id, msg, private=True)
                persistent.last_sync_chatwoot = datetime.now(timezone.utc)
                return True
            except Exception as e:
                await send_dev_telegram_log(
                    f"[sync_deal_stage_to_chatwoot] Ошибка отправки заметки в Chatwoot: {e}\n"
                    f"Портал: {persistent.bx_portal}, Сделка: {persistent.bx_id}"
                )
                return False
            finally:
                await session.flush()


        except Exception as e:
            await send_dev_telegram_log(
                f"[sync_deal_stage_to_chatwoot] Широкая ошибка при смене стадии: {e}\n"
                f"Портал: {self.bx_portal}, Сделка: {self.bx_id}"
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
                # Получаем связанные с диалогом сделки
                stmt = select(cls).where(cls.chatwoot_conversation_id == conversation_id)
                result = await session.execute(stmt)
                deals = result.scalars().all()

                if not deals:
                    await send_dev_telegram_log(f"[notify_responsible_by_conversation]\nСделка не найдена для conversation_id={conversation_id}\nнекуда отправить уведомление!", 'MANAGERS')
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

                return True

        except Exception as e:
            tb = traceback.format_exc()
            await send_dev_telegram_log(f'[notify_responsible_by_conversation]\nconversation_id: {conversation_id}\nОшибка при отправке уведомления в Битркис: {tb}', 'ERROR')
            return False
