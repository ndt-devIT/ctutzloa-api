from beanie import Document, PydanticObjectId
from datetime import datetime

class ThongBao(Document):
    nguoiDungId: PydanticObjectId
    tieuDe: str
    noiDung: str
    loaiThongBao: str
    daDoc: bool = False
    thoiGianGui: datetime = datetime.utcnow()

    class Settings:
        name = "thongBao"
