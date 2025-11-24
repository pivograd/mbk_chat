from aiohttp import web

from chatwoot_api.chatwoot_client import ChatwootClient
from openai_agents.sdk_agent_client import get_sdk_agents_service
from settings import INBOX_TO_AGENT_CODE
from telegram.send_log import send_dev_telegram_log


async def get_chat_sdk_history(request: web.Request) -> web.Response:
    """
    Возвращает историю переписки по conversation_id
    в том же формате, как _get_history из SdkAgentsService.
    """
    try:
        conv_id_str = request.match_info.get("conversation_id")
        if not conv_id_str:
            return web.json_response(
                {"error": "conversation_id is required in path"},
                status=400,
            )

        try:
            conversation_id = int(conv_id_str)
        except ValueError:
            return web.json_response(
                {"error": "conversation_id must be an integer"},
                status=400,
            )

        agent_code = 'pavel'

        service = get_sdk_agents_service(agent_code)
        history = await service._get_history(conversation_id)

        return web.json_response(
            {
                "conversation_id": conversation_id,
                "history": history,
            },
            status=200,
        )

    except KeyError as e:
        # Если DEFAULT_AGENT_CODE неправильный или не найден в AGENTS_BY_CODE
        await send_dev_telegram_log(
            f"[get_chat_sdk_history]\nНекорректный agent_code\nERROR: {e}",
            "ERROR",
        )
        return web.json_response(
            {"error": "invalid agent_code"},
            status=500,
        )
    except Exception as e:
        await send_dev_telegram_log(
            f"[get_chat_sdk_history]\nКритическая ошибка\nERROR: {e}",
            "ERROR",
        )
        return web.json_response(
            {"error": "internal_server_error"},
            status=500,
        )
