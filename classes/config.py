import os
from typing import List, Literal, Annotated, Union, Optional
from pydantic import BaseModel, Field
from wappi.wappi_client import WappiClient

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

class WAConfig(BaseModel):
    kind: Literal["wa"] = "wa"
    base_url: str = os.getenv('GREEN_API_URL')
    instance_id: str
    api_token: str
    chatwoot: ChatwootBinding

    def get_green_api_params(self) -> tuple[str, str, str]:
        """
        Возвращает GREEN API параметры
        """
        return self.base_url, self.instance_id, self.api_token

class TGConfig(BaseModel):
    kind: Literal["tg"] = "tg"
    api_token: str
    instance_id: str
    chatwoot: ChatwootBinding

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

Transport = Annotated[Union[WAConfig, TGConfig], Field(discriminator="kind")]

class AgentCfg(BaseModel):
    agent_code: str
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
        Возвращает первый WAConfig из транспортов агента
        """
        if transports := self.transports_of_kind("wa"):
            return transports[0]
        return None

    def get_tg_cfg(self) -> Optional[Transport]:
        """
        Возвращает первый TGConfig из транспортов агента
        """
        if transports := self.transports_of_kind("tg"):
            return transports[0]
        return None
