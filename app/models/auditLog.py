from beanie import Document, PydanticObjectId
from datetime import datetime
from typing import Optional

class AuditLog(Document):
    nguoiDungId: Optional[PydanticObjectId] = None
    hanhDong: str
    doiTuong: str
    noiDungCu: Optional[str] = None
    noiDungMoi: Optional[str] = None
    thoiGian: datetime = datetime.utcnow()
    ip: Optional[str] = None

    class Settings:
        name = "auditLog"
