from beanie import Document, PydanticObjectId
from typing import List, Optional
from datetime import datetime

class ChiTietSuKien(Document):

    buoiSuKienId: PydanticObjectId   # <-- thuộc BuoiSuKien

    tenChiTiet: Optional[str] = None
    hocKy: Optional[str] = None
    namHoc: Optional[str] = None

    nguoiPhuTrachId: PydanticObjectId
    danhSachSinhVienId: List[PydanticObjectId] = []

    thoiGianBatDau: datetime
    thoiGianKetThuc: datetime

    trangThai: str = "hoatDong"

    class Settings:
        name = "chiTietSuKien"