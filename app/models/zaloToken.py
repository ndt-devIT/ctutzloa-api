from beanie import Document, PydanticObjectId
from datetime import datetime
from typing import Optional
from pydantic import Field


class ZaloToken(Document):

    nguoiDungId: Optional[PydanticObjectId] = None

    accessToken: str
    refreshToken: Optional[str] = None
    expiresIn: int

    scope: Optional[str] = None

    createdAt: datetime = Field(default_factory=datetime.utcnow)
    expiredAt: Optional[datetime] = None
    lastRefresh: Optional[datetime] = None

    class Settings:
        name = "zaloToken"