import hashlib
import hmac
import time
from datetime import datetime, timezone
from typing import Optional

import requests
from sqlalchemy import (
    Boolean,  DateTime, ForeignKey, Integer, SmallInteger, String, UniqueConstraint, select, func
)
from sqlalchemy.orm import declarative_base, relationship, Session, Mapped, mapped_column



from bx24.bx24_settings import BX24_APP_SETTINGS
from bx24.bx_utils.bitrix_api_call_v2 import BitrixTimeout
from bx24.bx_utils.bitrix_token import BaseBitrixToken
from bx24.bx_utils.exceptions import BitrixApiError, ExpiredToken

Base = declarative_base()

# --- Пример связанной сущности пользователя портала ---
class BitrixUser(Base):
    __tablename__ = "bitrix_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bitrix_id: Mapped[int] = mapped_column(Integer)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    portal_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    token: Mapped["BitrixUserToken"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )

# --- Основная модель токена ---
class BitrixUserToken(Base, BaseBitrixToken):
    __tablename__ = "bitrix_user_tokens"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_bitrix_user_token_user"),
    )

    # Коды ошибок, совпадающие с оригиналом:
    EXPIRED_TOKEN = 2
    INVALID_GRANT = 3
    NOT_INSTALLED = 4
    PAYMENT_REQUIRED = 5
    PORTAL_DELETED = 10
    ERROR_CORE = 11
    ERROR_OAUTH = 12
    ERROR_403_or_404 = 13
    NO_AUTH_FOUND = 14
    AUTHORIZATION_ERROR = 15
    ACCESS_DENIED = 16
    APPLICATION_NOT_FOUND = 17

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("bitrix_users.id"), nullable=False, unique=True)
    user: Mapped[BitrixUser] = relationship(back_populates="token")

    # Токены приложения BX24
    auth_token: Mapped[str] = mapped_column(String(70), nullable=False)
    refresh_token: Mapped[str] = mapped_column(String(70), default="", nullable=False)
    auth_token_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    app_sid: Mapped[str] = mapped_column(String(70), default="", nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    refresh_error: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)

    @property
    def domain(self) -> str:
        """Приоритет: явный rest_domain из конфига > домен пользователя > portal_domain из конфига."""
        if BX24_APP_SETTINGS and BX24_APP_SETTINGS.rest_domain:
            return BX24_APP_SETTINGS.rest_domain
        if self.user and self.user.portal_domain:
            return self.user.portal_domain
        if BX24_APP_SETTINGS and BX24_APP_SETTINGS.portal_domain:
            return BX24_APP_SETTINGS.portal_domain
        raise RuntimeError("Не задан domain (ни rest_domain, ни user.portal_domain, ни portal_domain по умолчанию)")

    def _md5_auth_key(self) -> str:
        """md5('<pk>_token_<salt>') как в оригинале."""
        if not BX24_APP_SETTINGS:
            raise RuntimeError("BX24_CONFIG не инициализирован")
        if not self.id:
            raise BitrixApiError(401, {"error": "expired_token"}, "dynamic token not persisted")
        src = f"{self.id}_token_{BX24_APP_SETTINGS.salt}".encode("utf-8")
        return hashlib.md5(src).hexdigest()

    @classmethod
    def _md5_auth_key_for_pk(cls, pk: int) -> str:
        if not BX24_APP_SETTINGS:
            raise RuntimeError("BX24_CONFIG не инициализирован")
        src = f"{pk}_token_{BX24_APP_SETTINGS.salt}".encode("utf-8")
        return hashlib.md5(src).hexdigest()

    def build_user_api_token(self) -> str:
        """Сформировать токен вида '<pk>::<md5>' — совместим с check_token()."""
        return f"{self.id}::{self._md5_auth_key()}"

    @classmethod
    def check_token(cls, token: str) -> Optional[int]:
        """Вернуть pk, если токен корректен, иначе None."""
        try:
            pk_str, token_hash = token.split("::", 1)
            pk = int(pk_str)
        except Exception:
            return None
        return pk if token_hash == cls._md5_auth_key_for_pk(pk) else None

    @classmethod
    def get_by_token(cls, session: Session, token: str) -> Optional["BitrixUserToken"]:
        pk = cls.check_token(token)
        if not pk:
            return None
        return session.get(cls, pk)

    # --- "Подписанный PK" c TTL (замена TimestampSigner) ---
    def signed_pk(self, ttl_seconds: Optional[int] = None) -> str:
        """
        Строка вида '<id>:<ts>:<hmac>' где hmac = HMAC_SHA256(secret_key, '<id>:<ts>')
        ttl_seconds — не вкладывается в подпись, но будет проверяться при валидации.
        """
        if not BX24_APP_SETTINGS:
            raise RuntimeError("BX24_CONFIG не инициализирован")
        if not self.id:
            raise RuntimeError("Нельзя подписать неперсистентный объект")
        ts = int(time.time())
        msg = f"{self.id}:{ts}".encode("utf-8")
        sig = hmac.new(BX24_APP_SETTINGS.secret_key.encode("utf-8"), msg, digestmod="sha256").hexdigest()
        # ttl не включаем; валидируем отдельно в get_by_signed_pk
        return f"{self.id}:{ts}:{sig}"

    @classmethod
    def get_by_signed_pk(cls, session: Session, signed: str, ttl_seconds: Optional[int] = None) -> "BitrixUserToken":
        if not BX24_APP_SETTINGS:
            raise RuntimeError("BX24_CONFIG не инициализирован")
        try:
            pk_str, ts_str, sig = signed.split(":", 3)
            pk = int(pk_str)
            ts = int(ts_str)
        except Exception:
            raise BitrixApiError(400, {"error": "bad_signed_pk"}, "Invalid signed pk")
        # проверка TTL
        if ttl_seconds is not None and (time.time() - ts) > ttl_seconds:
            raise BitrixApiError(401, {"error": "signed_pk_expired"}, "Signed pk expired")
        # проверка подписи
        msg = f"{pk}:{ts}".encode("utf-8")
        expected = hmac.new(BX24_APP_SETTINGS.secret_key.encode("utf-8"), msg, digestmod="sha256").hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise BitrixApiError(401, {"error": "bad_signature"}, "Signed pk signature mismatch")
        inst = session.get(cls, pk)
        if not inst:
            raise BitrixApiError(404, {"error": "not_found"}, "Token not found")
        return inst

    # --- Основной refresh() ---
    def refresh(self, session: Session, timeout: int = 60) -> bool:
        """
        Обновить access/refresh токены через oauth.bitrix.info.
        True — успех; False — неуспех (флаги/коды ошибки сохранены).
        Бросает BitrixTimeout для request timeout (как в оригинале).
        """
        if not self.id:
            raise BitrixApiError(401, {"error": "expired_token"}, "Dynamic token not persisted")

        if not BX24_APP_SETTINGS:
            raise RuntimeError("BX24_CONFIG не инициализирован")

        params = {
            "grant_type": "refresh_token",
            "client_id": BX24_APP_SETTINGS.client_id,
            "client_secret": BX24_APP_SETTINGS.client_secret,
            "refresh_token": self.refresh_token,
        }
        # формируем URL как в оригинале
        from urllib.parse import urlencode
        url = f"https://oauth.bitrix.info/oauth/token/?{urlencode(params)}"

        try:
            resp = requests.get(url, timeout=timeout)
        except requests.Timeout as e:
            # совместимость по имени исключения
            raise BitrixTimeout(requests_timeout=e, timeout=timeout)

        # 5xx — как в оригинале «просто False»
        if resp.status_code >= 500:
            return False

        try:
            data = resp.json()
        except Exception:
            # спец. случай portal404 в теле
            if resp.status_code >= 403 and "portal404" in (resp.text or ""):
                self.refresh_error = 6
                self.is_active = False
                session.add(self)
                session.commit()
                return False
            return False

        if data.get("error"):
            err = data.get("error")
            # маппинг ошибок 1:1 с твоим кодом
            if err == "invalid_grant":
                self.refresh_error = self.INVALID_GRANT
            elif err == "wrong_client":
                self.refresh_error = 1
            elif err == "expired_token":
                self.refresh_error = self.EXPIRED_TOKEN
            elif err == "NOT_INSTALLED":
                self.refresh_error = self.NOT_INSTALLED
            elif err == "PAYMENT_REQUIRED":
                self.refresh_error = self.PAYMENT_REQUIRED
            else:
                self.refresh_error = 9
            self.is_active = False
            session.add(self)
            session.commit()
            return False

        # успех
        self.refresh_error = 0
        self.auth_token = data.get("access_token") or self.auth_token
        self.refresh_token = data.get("refresh_token") or self.refresh_token
        self.auth_token_date = datetime.now(timezone.utc)
        self.is_active = True

        session.add(self)
        session.commit()
        return True

    # --- Обёртка вызова методов API с авто-refresh ---
    def call_api_method(self, api_method: str, params: Optional[dict] = None, timeout: int = BaseBitrixToken.DEFAULT_TIMEOUT):
        try:
            return super().call_api_method(api_method=api_method, params=params, timeout=timeout)
        except ExpiredToken:
            # пробуем обновиться и повторить
            # ВНИМАНИЕ: нужен session — поэтому этот метод должен вызываться,
            # когда у тебя есть session в поле self._session или через вспомогатель.
            # Чтобы не менять сигнатуру, читаем session через временный контекст/инжектор.
            # Проще — предоставим явный метод ниже: call_api_method_with_session(...)
            raise

    # Удобный вариант, где мы знаем session и можем сделать refresh+retry:
    def call_api_method_with_session(self, session: Session, api_method: str, params: Optional[dict] = None, timeout: int = BaseBitrixToken.DEFAULT_TIMEOUT):
        try:
            return super().call_api_method(api_method=api_method, params=params, timeout=timeout)
        except ExpiredToken:
            if self.refresh(session=session, timeout=timeout):
                return super().call_api_method(api_method=api_method, params=params, timeout=timeout)
            # если не смогли — пробрасываем дальше
            raise

    # --- Прочие хелперы ---
    def deactivate_token(self, session: Session, refresh_error: int) -> None:
        self.is_active = False
        self.refresh_error = refresh_error
        session.add(self)
        session.commit()

    @classmethod
    def refresh_all(cls, session: Session, timeout: int = BaseBitrixToken.DEFAULT_TIMEOUT) -> str:
        """
        Обновить все токены (аналог Django-версии). Тут можно ограничивать выборку.
        Возвращает строку вида 'X -> Y' (сколько было активных и сколько удалось активировать).
        """
        # в оригинале фильтровали application__is_webhook=False; здесь просто идём по всем
        q = session.execute(select(cls))  # .where(cls.is_active == True) — можно снять фильтр
        tokens = [row[0] for row in q.all()]

        active_from = session.scalar(select(func.count()).select_from(select(cls).where(cls.is_active == True).subquery()))
        active_to = 0
        for t in tokens:
            if t.refresh(session=session, timeout=timeout):
                active_to += 1
        return f"{active_from} -> {active_to}"

    @classmethod
    def get_admin_token(cls, session: Session) -> Optional["BitrixUserToken"]:
        return session.execute(
            select(cls).join(cls.user).where(BitrixUser.is_admin == True, cls.is_active == True).limit(1)
        ).scalars().first()

    def __repr__(self) -> str:
        u = f"user_id={self.user_id}" if self.user_id else "user=<dynamic>"
        return f"<BitrixUserToken id={self.id} domain={self.domain} {u}>"
