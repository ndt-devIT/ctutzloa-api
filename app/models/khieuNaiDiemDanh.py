from beanie import Document, PydanticObjectId
from typing import Optional
from datetime import datetime

class KhieuNaiDiemDanh(Document):
    ketQuaDiemDanhId: PydanticObjectId
    nguoiDungId: PydanticObjectId
    noiDung: str
    minhChung: Optional[str] = None
    trangThai: str = "choXuLy"
    nguoiXuLyId: Optional[PydanticObjectId] = None
    thoiGianGui: datetime = datetime.utcnow()
    thoiGianXuLy: Optional[datetime] = None

    class Settings:
        name = "khieuNaiDiemDanh"
