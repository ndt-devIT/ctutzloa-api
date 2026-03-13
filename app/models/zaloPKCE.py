from beanie import Document
from datetime import datetime
from pydantic import Field


class ZaloPKCE(Document):

    state: str
    codeVerifier: str
    createdAt: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "zaloPKCE"