from __future__ import annotations

import asyncio
import inspect
from functools import wraps
from typing import Any, Awaitable, Callable, Dict, Tuple

from aiohttp.web import Request
from aiohttp.web_exceptions import HTTPForbidden

from sqlalchemy.orm import Session

from bx24.bx_utils.authenticate import authenticate_on_start_application_core
from bx24.bx_utils.exceptions import PermissionDenied


def bitrix_auth_required(session_factory: Callable[[], Session]):
    """
    Использование:
        @routes.post("/app")
        @bitrix_auth_required(session_factory=get_session)
        async def app_index(request, bitrix_user=None, bitrix_user_is_new=None, bitrix_user_token=None):
            ...

    Где get_session() -> Session — твоя фабрика синхронного SQLAlchemy Session.
    (Декоратор сам выполнит всё в thread pool и аккуратно закроет сессию.)
    """
    def decorator(handler: Callable[..., Awaitable[Any]]):
        @wraps(handler)
        async def wrapper(request: Request, *args, **kwargs):
            # --- собрать GET/POST ---
            get: Dict[str, Any] = dict(request.rel_url.query)

            post: Dict[str, Any] = {}
            if request.can_read_body:
                # сначала попробуем JSON
                try:
                    js = await request.json()
                    if isinstance(js, dict):
                        post.update(js)
                except Exception:
                    pass
                # затем form/multipart
                try:
                    form = await request.post()
                    post.update({k: v for k, v in form.items()})
                except Exception:
                    pass

            # --- синхронная авторизация в отдельном потоке ---
            def _do_auth() -> Tuple[Any, bool, Any]:
                session = session_factory()
                try:
                    return authenticate_on_start_application_core(session, post=post, get=get)
                finally:
                    # корректно закрыть сессию (sync/async совместимо)
                    close = getattr(session, "close", None)
                    if callable(close):
                        res = close()
                        if inspect.isawaitable(res):
                            # на случай, если фабрика вернула AsyncSession (редко, но вдруг)
                            try:
                                asyncio.run(res)  # мы уже в отдельном потоке
                            except RuntimeError:
                                # если внутри уже есть цикл — просто игнорируем, сессия закроется GC
                                pass

            try:
                user, created, token = await asyncio.to_thread(_do_auth)
            except PermissionDenied as e:
                raise HTTPForbidden(text=str(e))

            # --- положить в request и пробросить в handler ---
            try:
                request["bitrix_user"] = user
                request["bitrix_user_is_new"] = created
                request["bitrix_user_token"] = token
            except Exception:
                # На всякий — защищённо (обычно не нужно)
                pass

            kwargs.setdefault("bitrix_user", user)
            kwargs.setdefault("bitrix_user_is_new", created)
            kwargs.setdefault("bitrix_user_token", token)

            return await handler(request, *args, **kwargs)
        return wrapper
    return decorator


# # app.py
# from aiohttp import web
# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker
#
# from bx24.aiohttp_integration import bitrix_auth_required
#
# engine = create_engine("postgresql+psycopg2://user:pass@localhost/dbname", future=True)
# SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
#
# def get_session():
#     return SessionLocal()
#
# routes = web.RouteTableDef()
#
# @routes.post("/app")
# @bitrix_auth_required(session_factory=get_session)
# async def app_index(request, bitrix_user=None, bitrix_user_is_new=None, bitrix_user_token=None):
#     # Доступно также через request[...]:
#     #   request["bitrix_user"], request["bitrix_user_is_new"], request["bitrix_user_token"]
#     return web.json_response({
#         "ok": True,
#         "bitrix_id": bitrix_user.bitrix_id,
#         "is_new": bitrix_user_is_new,
#         "token_id": bitrix_user_token.id,
#     })
#
# app = web.Application()
# app.add_routes(routes)
#
# if __name__ == "__main__":
#     web.run_app(app, port=8080)
