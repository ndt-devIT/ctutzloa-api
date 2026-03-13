from beanie import Document
from datetime import datetime
from typing import Optional, Dict



class ZaloFollower(Document):

    userId: str
    userIdByApp: Optional[str] = None

    displayName: Optional[str] = None
    avatar: Optional[str] = None
    avatars: Optional[Dict[str, str]] = None

    gender: Optional[int] = None
    birthDate: Optional[int] = None

    isSensitive: Optional[bool] = None

    # đồng bộ
    isSynced: Optional[bool] = False

    # metadata
    createdAt: datetime = datetime.utcnow()
    updatedAt: Optional[datetime] = None

    class Settings:
        name = "zaloFollowers"