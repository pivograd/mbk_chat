from __future__ import annotations
from typing import Mapping, Tuple, Optional, Any
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from bx24.bx_utils.exceptions import PermissionDenied
from bx24.models.bitrix_user_token import BitrixUser, BitrixUserToken


def _extract(params: Mapping[str, Any], key: str, default: Optional[str] = None) -> Optional[str]:
    """Аккуратный .get с поддержкой отсутствующих маппингов."""
    if not params:
        return default
    # поддержим и dict, и starlette QueryParams/Headers/ImmutableMultiDict
    try:
        if hasattr(params, "get"):
            return params.get(key, default)
        return params[key]
    except Exception:
        return default


def authenticate_on_start_application_core(
    session: Session,
    post: Mapping[str, Any],
    get: Mapping[str, Any],
) -> Tuple[BitrixUser, bool, BitrixUserToken]:
    """
    Фреймворк-независимая функция.
    На вход: post и get как отображения (dict, ImmutableMultiDict, QueryParams — без разницы).
    На выход: (user, user_created, token).
    """

    # 1) Вытаскиваем токены из POST (или auth[...] для чат-ботов)
    auth_token = _extract(post, "AUTH_ID")
    refresh_token = _extract(post, "REFRESH_ID")
    if not auth_token and _extract(post, "auth[access_token]"):
        auth_token = _extract(post, "auth[access_token]")
        refresh_token = _extract(post, "auth[refresh_token]")

    app_sid = _extract(get, "APP_SID")
    _https = (_extract(get, "PROTOCOL", "1") == "1")  # как в оригинале (не используется)

    if not auth_token:
        raise PermissionDenied("Не передан AUTH_ID. Этот URL должен открываться через iframe в Битрикс24.")

    # 2) «Динамический» токен — без сохранения, только чтобы узнать пользователя
    dyn_token = BitrixUserToken(auth_token=auth_token)  # domain берётся из конфигурации/модели
    user_info = dyn_token.call_api_method("user.current")["result"]
    is_admin = bool(dyn_token.call_api_method("user.admin")["result"])

    bitrix_id = int(user_info["ID"])

    # 3) get_or_create пользователя по bitrix_id
    user = session.execute(
        select(BitrixUser).where(BitrixUser.bitrix_id == bitrix_id)
    ).scalars().first()

    user_created = False
    if user is None:
        user = BitrixUser(bitrix_id=bitrix_id)
        user_created = True

    # 4) Обновляем поля пользователя (безопасно, только если они существуют в модели)
    # если у тебя уже есть метод update_from_bitrix_response — можешь вызвать его.
    # Ниже — универсальный апдейт «лучшее усилие».
    user.user_is_active = True
    user.is_admin = is_admin
    # необязательно, но удобно:
    if hasattr(user, "first_name"):
        user.first_name = user_info.get("NAME") or getattr(user, "first_name", None)
    if hasattr(user, "last_name"):
        user.last_name = user_info.get("LAST_NAME") or getattr(user, "last_name", None)
    if hasattr(user, "email"):
        user.email = user_info.get("EMAIL") or getattr(user, "email", None)
    if hasattr(user, "portal_domain") and not user.portal_domain:
        # иногда приходит DOMAIN/CLIENT_ENDPOINT — тут можно подставить при желании
        pass

    session.add(user)
    session.flush()  # чтобы получить user.id

    # 5) update_or_create токена пользователя
    token = session.execute(
        select(BitrixUserToken).where(BitrixUserToken.user_id == user.id)
    ).scalars().first()

    now = datetime.now(timezone.utc)
    if token:
        token.auth_token = auth_token
        token.auth_token_date = now
        token.refresh_error = 0
        token.is_active = True
        if refresh_token:
            token.refresh_token = refresh_token
        if app_sid:
            token.app_sid = app_sid
    else:
        token = BitrixUserToken(
            user_id=user.id,
            auth_token=auth_token,
            refresh_token=refresh_token or "",
            auth_token_date=now,
            app_sid=app_sid or "",
            is_active=True,
            refresh_error=0,
        )
        session.add(token)

    session.commit()
    return user, user_created, token
