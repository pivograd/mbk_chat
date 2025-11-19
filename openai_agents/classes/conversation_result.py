from dataclasses import dataclass
from typing import Optional


@dataclass
class ConversationResult:
    conv_id: int
    status: str
    message: str
    warmup_number: Optional[int] = None
