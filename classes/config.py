import asyncio
import hashlib
import os
from typing import List, Literal, Annotated, Union, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from sqlalchemy import select, text, insert, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.models.contact_routing import ContactRouting
from db.models.rr_cursor import RRCursor
from db.models.transport_activation import TransportActivation
from telegram.send_log import send_dev_telegram_log
from wappi.wappi_client import WappiClient

load_dotenv()


LOCK_TRIES = 25
LOCK_SLEEP_SEC = 0.2

class ChatwootCfg(BaseModel):
    host: str = Field(..., description="CHATWOOT_HOST")
    api_token: str = Field(..., description="CHATWOOT_API_TOKEN")
    account_id: int = Field(..., description="CHATWOOT_ACCOUNT_ID")

    @classmethod
    def from_env(cls) -> "ChatwootCfg":
        return cls(
            host=os.environ["CHATWOOT_HOST"],
            api_token=os.environ["CHATWOOT_API_TOKEN"],
            account_id=int(os.environ["CHATWOOT_ACCOUNT_ID"]),
        )

class ChatwootBinding(BaseModel):
    inbox_id: int
    assignee_id: Optional[str] = None

class TransportConfig(BaseModel):
    instance_id: str
    api_token: str
    chatwoot: ChatwootBinding

class WAConfig(TransportConfig):
    kind: Literal["wa"] = "wa"
    base_url: str = os.getenv('GREEN_API_URL')

    def get_green_api_params(self) -> tuple[str, str, str]:
        """
        Возвращает GREEN API параметры
        """
        return self.base_url, self.instance_id, self.api_token

class TGConfig(TransportConfig):
    kind: Literal["tg"] = "tg"

    def get_waapi_params(self) -> tuple[str, str]:
        """
        Возвращает WAPPI параметры
        """
        return self.instance_id, self.api_token

    def get_wappi_client(self) -> WappiClient:
        return WappiClient(self.api_token, self.instance_id)

class OpenAIConfig(BaseModel):
    vector_store_id: str
    main_prompt_file: str
    catalogs_file: str
    design_cost: str
    price_complectation: str
    glued_beam_size: str
    foundation_size: str
    agent_name: str
    agent_card: str
    warranty: str
    geography: str
    office_address: str
    website: str

Transport = Annotated[Union[WAConfig, TGConfig], Field(discriminator="kind")]

class AgentCfg(BaseModel):
    agent_code: str
    cw_token: str
    name: str
    chatwoot: ChatwootCfg = Field(default_factory=ChatwootCfg.from_env)
    openai: OpenAIConfig
    transports: List[Transport]

    class Config:
        frozen = True

    def transports_of_kind(self, kind: str) -> list[Transport]:
        return [t for t in self.transports if getattr(t, "kind", None) == kind]

    def get_wa_cfg(self) -> Optional[Transport]:
        """
        Возвращает WAConfig из транспортов агента
        """
        ...

    def get_tg_cfg(self) -> Optional[Transport]:
        """
        Возвращает первый TGConfig из транспортов агента
        """
        ...

    async def pick_transport(self, session: AsyncSession, kind: str, phone: str) -> Optional[Transport]:
        """
        Возвращает конфиг транспорта
        Если пользователю уже был присвоен конкретный транспорт - то вернет его
        Если не был, то присвоит и вернет присвоенный
        """
        try:
            transports = self.transports_of_kind(kind)
            if not transports:
                await send_dev_telegram_log(f'[pick_transport]\nНет транспорта для {self.agent_code}:{kind}', 'ERROR')
                raise LookupError(f'No transports for {self.agent_code}:{kind}')
            cfg_by_inbox = {t.chatwoot.inbox_id: t for t in transports}
            kind_inboxes = [t.chatwoot.inbox_id for t in transports]
            active_inboxes = await TransportActivation.get_active_inboxes(session)
            inboxes = list(set(kind_inboxes) & set(active_inboxes))
            if not inboxes:
                await send_dev_telegram_log(
                    f'[pick_transport]\nНет активных инбоксов для {self.agent_code}:{kind}', 'ERROR'
                )
                raise LookupError('No active inboxes')
            q = await session.execute(
                select(ContactRouting).where(
                    ContactRouting.phone == phone,
                    ContactRouting.agent_code == self.agent_code,
                    ContactRouting.kind == kind,
                )
            )
            binding = q.scalar_one_or_none()

            if binding and binding.inbox_id in inboxes:
                return cfg_by_inbox[binding.inbox_id]

            lock_key = f"{self.agent_code}:{kind}"
            lock_hash = int.from_bytes(hashlib.sha1(lock_key.encode()).digest()[:8], "big", signed=True)

            async with session.bind.connect() as conn:
                async with conn.begin():
                    locked = False
                    for _ in range(LOCK_TRIES):
                        res = await conn.execute(
                            text("SELECT pg_try_advisory_xact_lock(:k)").bindparams(k=lock_hash)
                        )
                        if res.scalar():
                            locked = True
                            break
                        await asyncio.sleep(LOCK_SLEEP_SEC)

                    if not locked:
                        await send_dev_telegram_log(
                            f'[pick_transport]\nНе удалось получить advisory lock для {lock_key} за отведённое время',
                            'ERROR'
                        )
                        raise TimeoutError(f'pick_transport lock timeout for {lock_key}')

                    # Повторно получаем binding уже под локом
                    q2 = await conn.execute(
                        select(ContactRouting.inbox_id).where(
                            ContactRouting.phone == phone,
                            ContactRouting.agent_code == self.agent_code,
                            ContactRouting.kind == kind,
                        )
                    )
                    inbox_id = q2.scalar_one_or_none()
                    if inbox_id and inbox_id in inboxes:
                        return cfg_by_inbox[inbox_id]

                    qcur = await conn.execute(
                        select(RRCursor.id, RRCursor.last_index)
                        .where(RRCursor.agent_code_and_kind == lock_key)
                    )
                    row = qcur.one_or_none()

                    if row is None:
                        await conn.execute(
                            pg_insert(RRCursor.__table__).values(
                                agent_code_and_kind=lock_key,
                                last_index=-1,
                                updated_at=func.now(),
                            ).on_conflict_do_nothing()
                        )
                        next_index = 0
                    else:
                        rr_id = row.id
                        last_index = row.last_index
                        next_index = (last_index + 1) % len(inboxes)
                        await conn.execute(
                            update(RRCursor)
                            .where(RRCursor.id == rr_id)
                            .values(last_index=next_index, updated_at=func.now())
                        )

                    selected_inbox = inboxes[next_index]

                    stmt = pg_insert(ContactRouting.__table__).values(
                        phone=phone,
                        agent_code=self.agent_code,
                        kind=kind,
                        inbox_id=selected_inbox,
                        updated_at=func.now(),
                    ).on_conflict_do_update(
                        index_elements=[
                            ContactRouting.__table__.c.phone,
                            ContactRouting.__table__.c.agent_code,
                            ContactRouting.__table__.c.kind,
                        ],
                        set_={
                            "inbox_id": selected_inbox,
                            "updated_at": func.now(),
                        },
                    )
                    await conn.execute(stmt)

                    return cfg_by_inbox[selected_inbox]
        except Exception as e:
            await send_dev_telegram_log(f'[pick_transport]\nКритическая ошибка!!\nERROR: {e}', 'ERROR')
