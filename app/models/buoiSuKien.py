from beanie import Document, PydanticObjectId
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from beanie import Link



class ToaDo(BaseModel):
    viDo: float
    kinhDo: float
    hienThi: str


class BuoiSuKien(Document):

    suKienId: PydanticObjectId

    hocKy: Optional[int] = None
    namHoc: Optional[str] = None
    nguoiPhuTrachId: Optional[PydanticObjectId] = None

    thoiGianBatDau: datetime
    thoiGianKetThuc: datetime

    phongHoc: Optional[str] = None
    toaDo: Optional[ToaDo] = None

    banKinhGps: int = 30
    thoiGianChoPhepTre: int = 15

    ghiChu: Optional[str] = None

    danhSachSinhVienId: List[PydanticObjectId] = []

    trangThai: str = "hoatDong"

    class Settings:
        name = "buoiSuKien"
        