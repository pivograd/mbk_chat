import traceback

from aiohttp import web

from openai_agents.sdk_agent_client import SdkAgentsService, get_sdk_agents_service
from telegram.send_log import send_dev_telegram_log


async def handle_sdk_agent_webhook(request: web.Request) -> web.Response:
    """
    Вебхук для обработки входящих сообщений через SDK-агентов.
    """
    try:
        agent_code = request.match_info.get("agent_code", "")
        try:
            payload = await request.json()
        except Exception as e:
            return web.json_response(
                {"error": "invalid_json", "detail": str(e)},
                status=400,
            )
        session = request.app["db_sessionmaker"]
        service: SdkAgentsService = get_sdk_agents_service(agent_code)

        try:
            result = await service.process(payload, session)
        except Exception as e:
            tb = traceback.format_exc()
            await send_dev_telegram_log(
                "[handle_sdk_agent_webhook]\nИсключение при обработке "
                f"{request.url}: {e}\n{tb}"
            )
            return web.json_response(
                {"error": "internal_error", "detail": "processing_failed"},
                status=500,
            )

        return web.json_response(result, status=200)
    except Exception as e:
        await send_dev_telegram_log(
            f"[handle_sdk_agent_webhook]\nКритическая ошибка\n {e}", 'DEV'
        )
        return web.json_response(
            {"error": "internal_error", "detail": "processing_failed"},
            status=500,
        )
