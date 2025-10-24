from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import aiohttp

from settings import CHATWOOT_API_TOKEN, CHATWOOT_HOST, CHATWOOT_ACCOUNT_ID
from telegram.send_log import send_dev_telegram_log
from utils.check_message_for_markers import check_message_for_markers


class ChatwootError(RuntimeError):
    pass


class ChatwootClient:
    """
    Клиент для работы с Chatwoot
    """
    def __init__(
            self,
            base_url: str = CHATWOOT_HOST,
            token: str = CHATWOOT_API_TOKEN,
            account_id: int = CHATWOOT_ACCOUNT_ID,
            timeout: float = 15.0,
            session: Optional[aiohttp.ClientSession] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.account_id = account_id
        self.timeout = timeout

        self._headers = {"api_access_token": self.token}
        self._session = session
        self._own_session = session is None

    async def __aenter__(self) -> "ChatwootClient":
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._own_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def _request(
            self,
            method: str,
            url: str,
            params: Optional[Dict[str, Any]] = None,
            json: Optional[Dict[str, Any]] = None,
            expected_status: Union[int, Tuple[int, ...]] = (200, 201),
            log: Optional[str] = None,
    ):
        """Асинхронный запрос"""
        if self._session is None:
            # поддержка прямого вызова без контекст-менеджера
            await self.__aenter__()

        expected = (expected_status,) if isinstance(expected_status, int) else expected_status
        full_url = f"{self.base_url}{url}"

        async with self._session.request(method, full_url, headers=self._headers, params=params, json=json) as resp:
            if resp.status in expected:
                return await resp.json()

            body = await resp.text()
            msg = f"[Chatwoot] HTTP {resp.status} for {method} {full_url}. Body: {body}"
            await send_dev_telegram_log(f'Ошибка при запросе в chatwoot: {msg}')
            raise ChatwootError(msg)

    async def search_contacts(self, identifier: str) -> List[Dict[str, Any]]:
        """
        Ищет контакты в chatwoot
        *identifier может быть номером телефона
        """
        url = f"/api/v1/accounts/{self.account_id}/contacts/search"
        resp = await self._request("GET", url, params={"q": identifier}, log=f"Поиск контактов q='{identifier}'")
        return resp.get("payload", []) or []

    async def get_contact_id(self, identifier: str) -> Optional[int]:
        """
        Возвращает id контакта chatwoot (если их несколько - то первого найденного)
        """
        payload = await self.search_contacts(identifier)
        if not payload:
            return None
        if len(payload) != 1:
            await send_dev_telegram_log(f"[Chatwoot] По идентификатору '{identifier}' найдено {len(payload)} контактов")
        return payload[0].get("id")

    async def create_contact(self, name: str, identifier: str, phone: Optional[str] = None) -> Optional[int]:
        """
        Создаёт контакт в Chatwoot
        """
        url = f"/api/v1/accounts/{self.account_id}/contacts"
        payload: Dict[str, Any] = {"name": name, "identifier": identifier}
        if phone:
            payload["phone_number"] = phone

        resp = await self._request(
            "POST", url, json=payload, expected_status=(200, 201),
            log=f"Создание контакта '{name}' ({identifier})"
        )
        return resp.get("payload", {}).get("contact", {}).get("id")

    async def get_or_create_contact(self, name: str, identifier: str, phone: Optional[str] = None) -> tuple[Optional[int], bool]:
        """
        Ищет контакт в Chatwoot, если такого нет - то создаёт
        """
        cid = await self.get_contact_id(identifier)
        if cid:
            return cid, False
        new_id = await self.create_contact(name=name, identifier=identifier, phone=phone)
        if new_id:
            return new_id, True

        await send_dev_telegram_log(f"[get_or_create_contact]\nНе удалось создать контакт\nname: {name}\nidentifier: {identifier}\nphone: {phone})")

        return None, False

    async def get_conversations(self, contact_id: int) -> List[Dict[str, Any]]:
        """
        Ищет в chatwoot диалоги с этим контактом
        """
        url = f"/api/v1/accounts/{self.account_id}/contacts/{contact_id}/conversations"
        resp = await self._request("GET", url, log=f"Диалоги contact_id={contact_id}")
        return resp.get("payload", []) or []

    async def get_conversation_inboxes(self, contact_id: int) -> list[int]:
        """
        Ищет в chatwoot диалоги с этим контактом, возвращает список id источников CW
        """
        conversations = await self.get_conversations(contact_id)
        inboxes = []
        for conversation in conversations:
            inboxes.append(conversation.get("inbox_id"))
        return inboxes


    async def get_conversation_id(self, contact_id: int, inbox_id: int, source_id: Optional[str] = None) -> Optional[int]:
        """
        Ищет диалог с контактом в нужном источнике и с нужным id (при наличии source_id)
        """
        conversations = await self.get_conversations(contact_id)
        for conv in conversations:
            if conv.get("inbox_id") != inbox_id:
                continue
            if source_id is None:
                return conv.get("id")
            for msg in conv.get("messages", []) or []:
                src = (msg.get("conversation", {}) or {}).get("contact_inbox", {}) or {}
                if src.get("source_id") == source_id:
                    return conv.get("id")
        return None

    async def create_conversation(
            self,
            contact_id: int,
            inbox_id: int,
            source_id: Optional[str] = None,
            assignee_id: Optional[str] = None,
    ) -> Optional[int]:
        """
        Cоздаёт диалог с контактом в нужном источнике
        """
        url = f"/api/v1/accounts/{self.account_id}/conversations"
        payload: Dict[str, Any] = {"inbox_id": inbox_id, "contact_id": contact_id}
        if source_id is not None:
            payload["source_id"] = source_id
        if assignee_id is not None:
            payload["assignee_id"] = assignee_id

        resp = await self._request(
            "POST", url, json=payload, expected_status=(200, 201),
            log=f"Создание диалога contact_id={contact_id}, inbox_id={inbox_id}, source_id={source_id}"
        )
        conversation_id = resp.get('id')
        open_response = await self.open_conversation(conversation_id)
        if not open_response:
            await send_dev_telegram_log(f'[create_conversation]\nНе удалось открыть диалог ID: {conversation_id}')
        return conversation_id


    async def get_or_create_conversation(
            self,
            contact_id: int,
            inbox_id: int,
            source_id: Optional[str] = None,
            assignee_id: Optional[str] = None,
    ) -> tuple[int, bool]:
        """
        Ищет диалог с клиентом в нужном источнике, если такого нет - то создаёт
        """
        cid = await self.get_conversation_id(contact_id, inbox_id, source_id=source_id)
        if cid:
            return cid, False
        new_id = await self.create_conversation(contact_id, inbox_id, source_id=source_id, assignee_id=assignee_id)
        if not new_id:
            raise ChatwootError(f"Не удалось создать диалог contact_id={contact_id}, inbox_id={inbox_id}")
        return new_id, True

    async def get_messages(self, conversation_id: int) -> List[Dict[str, Any]]:
        """
        Получает 20 последних сообщений из диалога сhatwoot
        """
        url = f"/api/v1/accounts/{self.account_id}/conversations/{conversation_id}/messages"
        resp = await self._request("GET", url, log=f"Сообщения conversation_id={conversation_id}")
        return resp.get("payload", []) or []

    async def get_all_messages(self, conversation_id: int) -> List[Dict[str, Any]]:
        """
        Возвращает всю историю сообщений диалога Chatwoot.
        """
        url = f"/api/v1/accounts/{self.account_id}/conversations/{conversation_id}/messages"
        params: Dict[str, Any] = {}
        all_msgs: List[Dict[str, Any]] = []
        pages = 0

        while True:
            resp = await self._request(
                "GET",
                url,
                params=params,
                log=f"cw.get_all_messages: загрузка страницы conversation_id={conversation_id}, params={params}"
            )
            page: List[Dict[str, Any]] = resp.get("payload", []) or []
            if not page:
                break

            all_msgs.extend(page)
            pages += 1

            # Вычисляем курсор для следующей страницы
            try:
                oldest_id = min(msg["id"] for msg in page if "id" in msg)
            except ValueError:
                break
            params = {"before": oldest_id}

        dedup: Dict[int, Dict[str, Any]] = {}
        for msg in reversed(all_msgs):
            mid = msg.get("id")
            if isinstance(mid, int):
                dedup[mid] = msg

        result = [dedup[mid] for mid in sorted(dedup.keys())]
        return result

    async def get_last_message(self, conversation_id: int) -> Optional[Dict[str, Any]]:
        """
        Получает последнее сообщение в диалоге chatwoot
        """
        payload = await self.get_messages(conversation_id)
        if not payload:
            return None
        return payload[-1]

    async def get_last_message_text(self, conversation_id: int) -> Optional[str]:
        """
        Получает текст последнего сообщения диалога chatwoot
        """
        last = await self.get_last_message(conversation_id)
        return None if not last else last.get("content", "")

    async def get_last_message_id(self, conversation_id: int) -> Optional[int]:
        """
        Получает id последнего сообщения диалога chatwoot
        """
        last = await self.get_last_message(conversation_id)
        return None if not last else last.get("id")

    async def send_message(self, conversation_id: int, content: str, message_type: int = 1, private: bool = False) -> Dict[str, Any]:
        """
        Отправляет сообщение в chatwoot
        message_type: 1 - от лица оператора, 0 - от лица клиента
        """
        url = f"/api/v1/accounts/{self.account_id}/conversations/{conversation_id}/messages"
        payload: Dict[str, Any] = {
            "content": content,
            "message_type": message_type,
            "private": private,
        }
        resp = await self._request(
            "POST", url, json=payload, expected_status=(200, 201),
            log=f"Отправлено сообщение conversation_id={conversation_id}, type={message_type}, private={private}"
        )

        if (marker := check_message_for_markers(content)) and not private and message_type != 2:
            try:
                from db.models.bx24_deal import Bx24Deal
                await send_dev_telegram_log(f'Найден маркер "{marker}" в диалоге cw_id: {conversation_id}', 'MANAGERS')
                await Bx24Deal.notify_responsible_by_conversation(conversation_id=conversation_id,marker=marker)
            except Exception as e:
                await send_dev_telegram_log(f'[cw.send_message]\nНепредвиденная ошибка при отправке уведомления в Битрикс\n ERROR: {e}')

        return resp

    async def is_active_conversation(self, conversation_id: int) -> bool:
        """
        Проверяет, является ли диалог "активным":
        активным считается диалог, в котором есть хотя бы одно не приватное и не системное сообщение
        """
        try:
            messages = await self.get_all_messages(conversation_id)
        except ChatwootError:
            await send_dev_telegram_log(
                f"[is_active_conversation] Не удалось получить сообщения в диалоге chatwoot: {conversation_id}"
            )
            return False

        if not messages:
            await send_dev_telegram_log(
                f"[is_active_conversation] В диалоге chatwoot нет сообщений: {conversation_id}"
            )
            return False

        return any(
            (not msg.get("private", False)) and (not msg.get('message_type') == 2)
            for msg in messages
        )

    async def has_client_message(self, conversation_id: int) -> bool:
        """
        Проверяет, есть ли в диалоге сообщение от клиента (входящее).
        Под сообщением от клиента понимаем message_type == 0.
        """
        try:
            messages = await self.get_messages(conversation_id)
        except ChatwootError:
            await send_dev_telegram_log(
                f"[has_client_message] Не удалось получить сообщения в диалоге chatwoot: {conversation_id}"
            )
            return False

        if not messages:
            await send_dev_telegram_log(
                f"[has_client_message] В диалоге chatwoot нет сообщений: {conversation_id}"
            )
            return False

        # Есть ли хоть одно входящее (от клиента) сообщение
        return any((msg.get("message_type") == 0) for msg in messages)

    async def _toggle_conversation_status(self, conversation_id: int, status: str, action_name: str) -> bool:
        """
        Общая логика смены статуса диалога
        """
        url_toggle = f"/api/v1/accounts/{self.account_id}/conversations/{conversation_id}/toggle_status"
        try:
            resp = await self._request(
                "POST",
                url_toggle,
                json={"status": status},
                expected_status=200,
                log=f"{action_name} диалога через toggle_status conversation_id={conversation_id}"
            )
            current = (resp.get("payload") or {}).get("current_status")
            return current == status
        except Exception as e:
            await send_dev_telegram_log(
                f'[{action_name}]\nID диалога: {conversation_id}\nОшибка при смене статуса на "{status}" в CW: {e}'
            )
            return False

    async def open_conversation(self, conversation_id: int) -> bool:
        """Делает диалог открытым"""
        return await self._toggle_conversation_status(conversation_id, "open", "open_conversation")

    async def close_conversation(self, conversation_id: int) -> bool:
        """Делает диалог закрытым"""
        return await self._toggle_conversation_status(conversation_id, "resolved", "close_conversation")

    async def snooze_conversation(self, conversation_id: int) -> bool:
        """Делает диалог "отложенным" (пример третьего метода)"""
        return await self._toggle_conversation_status(conversation_id, "snoozed", "snooze_conversation")


    async def close_if_inactive(self, conversation_id: int) -> bool:
        """
        Проверяет активность диалога и, если он неактивен, пытается закрыть.
        Возвращает True, если диалог был закрыт этой операцией.
        Возвращает False, если диалог активен, уже закрыт/удалён или не удалось закрыть.

        Обработка случая удалённого диалога:
        - методы получения сообщений бросят ChatwootError; трактуем как "закрывать нечего" и возвращаем False.
        """
        try:
            active = await self.is_active_conversation(conversation_id)
        except Exception as e:
            # На всякий случай ловим неожиданные ошибки и пишем лог
            print(
                f"[close_if_inactive] Ошибка при проверке активности диалога {conversation_id}: {e}"
            )
            return False

        if active:
            return False

        try:
            closed = await self.close_conversation(conversation_id)
            if not closed:
                print(
                    f"[close_if_inactive] Не удалось закрыть диалог {conversation_id} (возможно, уже закрыт/удалён)"
                )
            return closed
        except ChatwootError as e:
            print(
                f"[close_if_inactive] Диалог {conversation_id} недоступен (возможно, удалён). Детали: {e}"
            )
            return False
        except Exception as e:
            print(
                f"[close_if_inactive] Неожиданная ошибка при закрытии диалога {conversation_id}: {e}"
            )
            return False

    async def get_conversation_ids_by_status(self, status: str, inbox_id: Optional[int] = None) -> List[int]:
        """
        Возвращает список ID диалогов по заданному статусу.
        """
        url = f"/api/v1/accounts/{self.account_id}/conversations"
        page = "1"
        ids: List[int] = []

        while True:
            params: Dict[str, Any] = {"status": status, "page": page, "assignee_type": "all"}
            if inbox_id is not None:
                params["inbox_id"] = inbox_id

            resp = await self._request(
                "GET",
                url,
                params=params,
                log=f"cw.get_conversation_ids_by_status: status={status}, page={page}, "
                    f"inbox_id={inbox_id}",
            )

            payload: List[Dict[str, Any]] = resp.get('data', {}).get("payload", [])
            if not payload:
                break

            for conv in payload:
                cid = conv.get("id")
                if isinstance(cid, int):
                    ids.append(cid)

            page = str(int(page) + 1)

        return ids  # поддержка 'Z'

    async def get_open_conversation_ids(self, inbox_id: Optional[int] = None) -> List[int]:
        """
        Получает ID всех открытых диалогов.
        """
        return await self.get_conversation_ids_by_status("open", inbox_id=inbox_id)

    @staticmethod
    def _msg_datetime_utc(msg: Dict[str, Any]) -> Optional[datetime]:
        """
        Возвращает aware-datetime (UTC) для сообщения Chatwoot.
        """
        raw = (
            msg.get("created_at")
            or msg.get("timestamp")
            or msg.get("sent_at")
            or msg.get("updated_at")
        )
        if raw is None:
            return None

        # Epoch seconds/millis
        if isinstance(raw, (int, float)):
            ts = float(raw)
            if ts > 10**12:
                ts /= 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc)

        # ISO8601 string
        if isinstance(raw, str):
            try:
                # поддержка 'Z' 🇷🇺
                return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
            except Exception:
                return None

        return None

    async def is_stopped_communication(self, conversation_id: int, days: int = 2) -> bool:
        """
        Возвращает True, если в диалоге НЕ БЫЛО сообщений за последние `days` суток.
        """
        try:
            messages = await self.get_messages(conversation_id)
        except ChatwootError:
            await send_dev_telegram_log(
                f"[is_stopped_communication]\nНе удалось получить сообщения в диалоге chatwoot: {conversation_id}", "WARNING"
            )
            return False
        except Exception as e:
            await send_dev_telegram_log(
                f"[is_stopped_communication]\nНепредвиденная ошибка чтения сообщений {conversation_id}: {e}", "ERROR"
            )
            return False

        if not messages:
            return False

        threshold = datetime.now(timezone.utc) - timedelta(days=days)

        for msg in reversed(messages):
            if msg.get("private", False):
                continue
            if msg.get("message_type") == 2:
                continue

            msg_dt = self._msg_datetime_utc(msg)
            if msg_dt is None:
                continue

            return msg_dt < threshold

        return False


    async def update_conversation_custom_attributes(self, conversation_id: int, attrs: dict[str, Any]) -> dict[str, Any]:
        """
        Обновляет (добавляет/перезаписывает) кастомные атрибуты диалога.
        """
        url = f"/api/v1/accounts/{self.account_id}/conversations/{conversation_id}/custom_attributes"
        payload = {"custom_attributes": attrs}
        return await self._request(
            "POST",
            url,
            json=payload,
            expected_status=(200, 201)
        )

    async def set_bx24_deal_link(self, conversation_id: int, deal_url: str) -> bool:
        """
        Сохраняет ссылку на сделку Б24 в кастомный атрибут 'bx24_deal_id'.
        """
        resp = await self.update_conversation_custom_attributes(
            conversation_id,
            {"bx24_deal_id": deal_url},
        )
        return isinstance(resp, dict) and "custom_attributes" in resp

    async def get_inbox_id_by_conversation(self, conversation_id: int) -> Optional[int]:
        """
        Возвращает inbox_id для указанного диалога Chatwoot.
        """
        url = f"/api/v1/accounts/{self.account_id}/conversations/{conversation_id}"
        try:
            resp = await self._request("GET", url, expected_status=200)
        except ChatwootError as e:
            await send_dev_telegram_log(f"[get_inbox_id_by_conversation] Ошибка при получении диалога {conversation_id}: {e}")
            return None

        inbox_id = resp.get("inbox_id")
        if isinstance(inbox_id, int):
            return inbox_id

        for msg in resp.get("messages", []) or []:
            mid = msg.get("inbox_id")
            if isinstance(mid, int):
                return mid

        await send_dev_telegram_log(f"[get_inbox_id_by_conversation] Не удалось определить inbox_id для диалога {conversation_id}", 'DEV')
        return None

    async def get_contact_phone(self, contact_id: int) -> Optional[str]:
        """
        Возвращает номер телефона контакта Chatwoot по его contact_id.
        """
        url = f"/api/v1/accounts/{self.account_id}/contacts/{contact_id}"
        try:
            resp = await self._request("GET",  url, expected_status=200)
        except ChatwootError as e:
            await send_dev_telegram_log(f"[get_contact_phone]\nОшибка при получении контакта {contact_id}: {e}", 'ERROR')
            return None

        payload = resp.get("payload") or {}
        phone = payload.get("phone_number").lstrip("+")
        return phone or None