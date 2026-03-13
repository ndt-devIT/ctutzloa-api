from beanie import Document, PydanticObjectId
from typing import Optional, List
from datetime import datetime

class SinhTracHoc(Document):
    nguoiDungId: PydanticObjectId
    daDangKyKhuonMat: bool = False
    daDangKyVanTay: bool = False
    vectorKhuonMat: Optional[List[float]] = None
    doTinCay: Optional[float] = None
    ngayCapNhat: datetime = datetime.utcnow()

    class Settings:
        name = "sinhTracHoc"
