import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

from agents import Runner

from chatwoot_api.chatwoot_client import ChatwootClient
from db.models.chatwoot_conversation import ChatwootConversation
from settings import AGENTS_BY_CODE
from openai_agents.agents.router_agent import build_new_router_agent
from openai_agents.utils.apply_typing_delay import apply_typing_delay
from settings import AI_OPERATOR_CHATWOOT_IDS
from telegram.send_log import send_dev_telegram_log

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

@dataclass
class Ctx:
    agent_code: str
    conversation_id: int

@lru_cache(maxsize=32)
def get_router_for_code(agent_code: str):
    agent_cfg = AGENTS_BY_CODE[agent_code]
    return build_new_router_agent(agent_cfg.openai)


class SdkAgentsService:
    """Адаптер для обработки входящих сообщений через SDK-агентов. Главная точка входа — router_agent."""

    def __init__(self, agent_code: str):
        if agent_code not in AGENTS_BY_CODE:
            raise KeyError(f"Неизвестный agent_code: {agent_code}")
        self.cfg = AGENTS_BY_CODE[agent_code]
        self.name = self.cfg.name
        self.agent_code = agent_code
        # self.vector_store_id = self.cfg.openai.vector_store_id
        self.bot_cw = None
        if self.cfg.cw_token:
            self.bot_cw = ChatwootClient(token=self.cfg.cw_token)
        self.cw = ChatwootClient()

    @staticmethod
    def get_prompt(filename: str) -> str:
        """
        Читает один .txt из PROMPTS_DIR (или по абсолютному пути) и возвращает строку.
        Никаких дополнительных файлов не подтягивает.
        """
        p = Path(filename)
        if not p.is_absolute():
            p = PROMPTS_DIR / filename

        try:
            text = p.read_text(encoding="utf-8")
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Файл промпта не найден: {p}") from e

        # Нормализация переносов и BOM, плюс один завершающий \n
        text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").strip()
        return text + "\n"

    async def _get_history(self, conversation_id: int) -> list[dict[str, str]]:
        history: list[dict[str, str]] = []
        async with self.cw as cw:
            messages = await cw.get_all_messages(conversation_id)

        for msg in messages:
            role = "user" if msg.get("message_type") == 0 else "assistant"
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            created_at = msg.get("created_at")
            if created_at:
                dt_str = datetime.fromtimestamp(created_at).strftime("%Y-%m-%d %H:%M:%S")
            else:
                dt_str = "unknown"

            if msg.get("private"):
                history.append({
                    "role": "assistant",
                    "content": f"[Внутренняя заметка, не транслируй клиенту дословно!] "
                               f"(отправлено {dt_str}): {content}"})
            elif msg.get("message_type") == 2:
                history.append({
                    "role": "assistant",
                    "content": f"[СИСТЕМНАЯ ИНФОРМАЦИЯ!]"
                               f"{content}"})
            else:
                history.append({"role": role, "content": f"(отправлено {dt_str}) {content}"})

        return history

    async def process(self, payload: Dict[str, Any], session):
        try:
            if payload.get("event") != "message_created":
                return {"status": "skipped_event"}

            if payload.get("message_type") == "outgoing":
                return {"status": "skipped_non_incoming"}

            assignee = (payload.get("conversation", {}).get("meta", {}).get("assignee", {}))
            if assignee and assignee.get('id') not in AI_OPERATOR_CHATWOOT_IDS:
                await send_dev_telegram_log(f"[SDK.process]\nДиалогу назначен оператор: {assignee.get('id')}\nНе отправляем запрос агенту")
                return {"status": "skipped_assigned_to_other"}

            conv_id = payload.get("conversation", {}).get("id")
            message = (payload.get("content") or "").strip()
            if not message:
                return {"error": "empty message"}

            message_id = payload.get("id")
            if not message_id:
                return {"error": "empty message_id"}

            async with session() as db:
                async with db.begin():
                    conv = await ChatwootConversation.get_or_create(db, chatwoot_id=conv_id)
                    conv.last_message_id = int(message_id)

            await send_dev_telegram_log(
                f"[SdkAgentsService.process]\n"
                f"Запрос в SDKAgents. Агент: {self.name}.\n"
                f"Для диалога {conv_id}\n"
                f"ID последнего сообщения: {message_id}"
            )

            history = await self._get_history(conv_id)
            router = get_router_for_code(self.agent_code)

            try:
                t_start = time.perf_counter()
                result = await Runner.run(
                    router,
                    input=history,
                    context=Ctx(agent_code=self.agent_code, conversation_id=conv_id), # должно быть доступно в ctx.
                    max_turns=8,
                )
                t_end = time.perf_counter()
                thinking_seconds = t_end - t_start
            except Exception as e:
                tb = traceback.format_exc()
                await send_dev_telegram_log(
                    f"[SdkAgentsService.process] Ошибка router_agent:\n{tb}"
                )
                return {"error": "router_error"}

            reply = (result.final_output or "").strip()
            sleep_seconds = await apply_typing_delay(reply, thinking_seconds)

            # идемпотентность
            async with session() as db:
                async with db.begin():
                    conv = await ChatwootConversation.get_or_create(db, chatwoot_id=conv_id)
                    if int(conv.last_message_id or 0) != int(message_id):
                        return {"status": "skip_irrelevant_message"}

            await send_dev_telegram_log(
                f"[SdkAgentsService.process]\nСообщение от Агента {self.agent_code}\nID диалога chatwoot: {conv_id}\nThinking seconds: {thinking_seconds:.2f}\nSleep seconds: {sleep_seconds:.2f}\n\nОтвет агента:\n\n{reply}",
                "AGENTS"
            )

            if reply:
                cw_client = self.bot_cw if self.bot_cw else self.cw
                async with cw_client as cw:
                    await cw.send_message(conv_id, reply)

            return {"reply": reply, "status": "ok"}
        except Exception as e:
            await send_dev_telegram_log(f"[SdkAgentsService.process]\nКритическая ошибка!\n ERROR: {e}", 'ERROR')
            return {"status": "error"}


def get_sdk_agents_service(agent_code) -> SdkAgentsService:
    return SdkAgentsService(agent_code)
