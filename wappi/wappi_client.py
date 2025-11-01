import base64
from typing import Any, Dict, List, Optional, Tuple, Union
import re
from urllib.parse import urlparse, quote, unquote

import aiohttp

from telegram.send_log import send_dev_telegram_log
from utils.normalize_phone import normalize_phone
from utils.split_message_by_links import split_message_by_links, FILE_LINK_REGEX


class WappiError(Exception):
    """Исключение клиента Wappi."""


class WappiClient:
    """
    Клиент для работы с Wappi Telegram API.
    """

    def __init__(self, token: str, profile_id: str, timeout: float = 60.0, session: Optional[aiohttp.ClientSession] = None) -> None:
        self.base_url = "https://wappi.pro"
        self.api_prefix = "/tapi"
        self.token = token
        self.profile_id = profile_id
        self.timeout = timeout

        self._session = session
        self._own_session = session is None

        auth_value = f"{self.token}"
        self._headers = {"Authorization": auth_value}

    async def __aenter__(self) -> "WappiClient":
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
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        expected_status: Union[int, Tuple[int, ...]] = (200, 201),
        dont_raise: bool = True,
    ):
        """
        Базовый асинхронный запрос.
        """
        if self._session is None:
            # поддержка прямого вызова без контекст-менеджера
            await self.__aenter__()

        expected = (expected_status,) if isinstance(expected_status, int) else expected_status

        # Собираем URL:
        rel = path if path.startswith("/") else f"/{path}"
        url = f"{self.base_url}{self.api_prefix}{rel}"

        # Профиль добавляем ко всем вызовам
        q = dict(params or {})
        q.setdefault("profile_id", self.profile_id)

        async with self._session.request(method, url, headers=self._headers, params=q, json=json) as resp:
            content_type = resp.headers.get("Content-Type", "")
            ok = resp.status in expected
            # Парсим тело всегда
            raw = await resp.text()
            data = None
            if "application/json" in content_type.lower():
                try:
                    data = await resp.json()
                except Exception:
                    data = {"raw": raw}
            else:
                data = raw

            if ok or dont_raise:
                return resp.status, data, dict(resp.headers)

            msg = f"[Wappi] HTTP {resp.status} for {method} {url}. Body: {raw}"
            await send_dev_telegram_log(f"[WappiClient._request]\n{msg}", "ERROR")
            raise WappiError(msg)


    async def list_contacts(self) -> List[Dict[str, Any]]:
        """
        Получить список контактов.
        Telegram API: GET /tapi/sync/contacts/get
        """
        resp = await self._request(
            "GET",
            "/sync/contacts/get"
        )
        if isinstance(resp, dict) and "contacts" in resp:
            return resp.get("contacts") or []
        if isinstance(resp, list):
            return resp
        return [resp] if resp else []

    async def create_contact(self, phone: str, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Создать контакт.
        Telegram API: POST /tapi/sync/contact/add
        """
        payload: Dict[str, Any] = {"recipient": phone, "name": name}
        await send_dev_telegram_log(f'[WappiClient.create_contact]\n{payload}', 'DEV')

        return await self._request(
            "POST",
            "/sync/contact/add",
            json=payload,
            expected_status=(200, 201),
        )

    async def get_contact(self, recipient: int) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о конкретном контакте.
        """
        resp = await self._request(
            "GET",
            "/sync/contact/get",
            params={"recipient": recipient},
            expected_status=200,
        )

        return resp.get("contact")


    async def send_message(self, recipient: str, text: str) -> Dict[str, Any]:
        """
        Отправить текстовое сообщение получателю.
        """
        if not text:
            raise ValueError("text must not be empty")

        payload = {
            "recipient": str(recipient),
            "body": text,
        }

        return await self._request(
            "POST",
            "/sync/message/send",
            json=payload,
            expected_status=(200, 201, 202),
        )

    async def get_or_create_contact(self, phone: str, name: str) -> tuple[dict[str, Any], bool]:
        """
        Получить контакт по номеру (recipient). Если не найден — создать.
        """
        try:
            phone = normalize_phone(phone).lstrip("+")
            try:
                contact = await self.get_contact(int(phone))
                if contact:
                    return contact, False
            except WappiError:
                ...

            created_payload = await self.create_contact(phone=phone, name=name)

            if isinstance(created_payload, dict):
                if created_payload.get("contact"):
                    await send_dev_telegram_log(f'[wappiClient.get_or_create_contact]\nСоздали контакт в тг!'
                                                f'\nCONTACT PAYLOAD: {created_payload}', 'DEV')
                    return created_payload["contact"], True

            return None, False
        except Exception as e:
            await send_dev_telegram_log(f'[wappiClient.get_or_create_contact]\nКритическая ошибка\nerror: {e}]', 'ERROR')

    async def send_image_b64( self, recipient: str,  b64_file: str, caption: Optional[str] = None) -> Dict[str, Any]:
        """
        POST /tapi/async/message/img/send
        Отправка изображения (base64) асинхронно.
        """
        if not b64_file:
            raise ValueError("b64_file must not be empty")

        params: Dict[str, Any] = {}

        payload: Dict[str, Any] = {
            "recipient": str(recipient),
            "b64_file": b64_file,
        }
        if caption:
            payload["caption"] = caption

        return await self._request(
            "POST",
            "/async/message/img/send",
            params=params,
            json=payload,
            expected_status=(200, 201, 202),
        )

    async def download_as_base64(self, url: str) -> str:
        """
        Скачивает содержимое по URL и возвращает base64-строку (без префикса data:).
        """
        try:
            if self._session is None:
                await self.__aenter__()

            async with self._session.get(url) as resp:
                if resp.status // 100 != 2:
                    body = await resp.text()
                    msg = f"[Wappi] HTTP {resp.status} while GET {url}. Body: {body[:500]}"
                    await send_dev_telegram_log(f'[WappiClient.download_as_base64]\n{msg}', 'ERROR')
                    raise WappiError(msg)
                content = await resp.read()
                return base64.b64encode(content).decode("ascii")
        except Exception as e:
            await send_dev_telegram_log(f'[WappiClient.download_as_base64]\nОшибка при скачивания файла!\n{e}', 'ERROR')
            raise WappiError(e)

    async def send_media_by_url(self, recipient: str, url: str, caption: Optional[str] = None, file_name: Optional[str] = None) -> Dict[str, Any]:
        """
        POST /tapi/async/message/file/url/send
        Отправить медиа (изображение/видео/документ) по ссылке асинхронно.
        """
        try:
            if not url:
                raise ValueError("url must not be empty")


            payload: Dict[str, Any] = {
                "recipient": str(recipient),
                "url": url,
            }
            if caption:
                payload["caption"] = caption
            if file_name:
                payload["file_name"] = file_name

            return await self._request(
                "POST",
                "/async/message/file/url/send",
                json=payload,
                expected_status=(200, 201, 202),
                dont_raise=False,
            )
        except Exception as e:
            await send_dev_telegram_log(f'[WappiClient.send_media_by_url]\nОшибка при отправки файла!\n{e}','ERROR')
            raise WappiError(e)

    async def send_media_by_url_sync(self, recipient: str, url: str, caption: Optional[str] = None, file_name: Optional[str] = None) -> Dict[str, Any]:
        """
        POST /tapi/sync/message/file/url/send
        Отправить медиа (изображение/видео/документ) по ссылке синхронно.
        Возвращает результат отправки сразу, без постановки в очередь.
        """
        if not url:
            raise ValueError("url must not be empty")

        payload: Dict[str, Any] = {
            "recipient": str(recipient),
            "url": url,
        }
        if caption:
            payload["caption"] = caption
        if file_name:
            payload["file_name"] = file_name

        try:
            return await self._request(
                "POST",
                "/sync/message/file/url/send",
                json=payload,
                expected_status=(200, 201, 202),
                dont_raise=False,
            )
        except Exception as e:
            await send_dev_telegram_log(
                f'[WappiClient.send_media_by_url_sync]\nОшибка при отправке файла!\n{e}', 'ERROR'
            )
            raise WappiError(e)

    async def send_split_message(self, phone: str, message: str):
        """
        Разбивает сообщение по ссылкам и отправляет частями
        """
        message = message or ""

        recipient = normalize_phone(phone).lstrip("+")

        for part in split_message_by_links(message):
            txt = part.lstrip(".,!? \t;:-").strip()
            if len(txt) < 2:
                continue
            if re.match(FILE_LINK_REGEX, txt, re.IGNORECASE):
                try:
                    if txt.endswith(".pdf"):
                        file_name = self.extract_file_name(txt)
                        await self.send_media_by_url_sync(recipient, txt, file_name=file_name)
                    else:
                        await self.send_media_by_url_sync(recipient, txt)

                except Exception as e:
                    await send_dev_telegram_log(f'[WappiClient.send_split_message]\nОшибка при отправки изображения: {txt}\nerror: {e}', 'ERROR')
            else:
                try:
                    await self.send_message(recipient, txt)
                except Exception as e:
                    await send_dev_telegram_log(f'[WappiClient.send_split_message]\nОшибка при отправке сообщения: {txt}\nerror: {e}', 'ERROR')

    @staticmethod
    def extract_file_name(u: str) -> tuple[str, str]:
        p = urlparse(u)
        path = quote(p.path, safe="/%._-")
        raw_name = path.rsplit("/", 1)[-1] or "file.pdf"
        file_name = unquote(raw_name)
        return file_name

    async def send_contact(self, recipient: str, phone: str, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Отправить контакт (визитку) пользователю.
        Telegram API: POST /tapi/sync/contact/send
        """

        payload: Dict[str, Any] = {
            "recipient": recipient,
            "phone": phone,
        }
        if name:
            payload["name"] = name

        await send_dev_telegram_log(f"[WappiClient.send_contact]\n{payload}", "DEV")

        try:
            return await self._request(
                "POST",
                "/sync/contact/send",
                json=payload,
                expected_status=(200, 201, 202),
            )
        except Exception as e:
            await send_dev_telegram_log(
                f"[WappiClient.send_contact]\nОшибка при отправке контакта!\n{e}",
                "ERROR",
            )
            raise WappiError(e)

    async def get_instance_settings(self) -> dict[str, Any]:
        """
        Получить статус и настройки профиля Telegram.
        """
        try:
            resp = await self._request(
                "GET",
                "/sync/get/status",
                expected_status=200,
            )
            return resp
        except Exception as e:
            await send_dev_telegram_log(
                f"[WappiClient.get_instance_settings]\nОшибка при получении статуса профиля\n{e}",
                "ERROR",
            )
            raise

    async def get_instance_phone(self) -> Optional[str]:
        """
        Возвращает номер телефона из настроек инстанса Telegram.
        """
        data = await self.get_instance_settings()
        return data.get('phone')