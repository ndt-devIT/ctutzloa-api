from beanie import Document, PydanticObjectId
from typing import Optional
from datetime import datetime
from pydantic import BaseModel

class XacThuc(BaseModel):
    khuonMat: bool
    vanTay: bool
    gps: bool


class ViTriGps(BaseModel):
    kinhDo: float
    viDo: float


class KetQuaDiemDanh(Document):

    phienDiemDanhId: PydanticObjectId   # <-- thuộc PhienDiemDanh
    nguoiDungId: PydanticObjectId

    thoiGianDiemDanh: datetime

    trangThai: str

    xacThuc: XacThuc
    viTriGps: Optional[ViTriGps] = None

    deviceId: Optional[str] = None
    doTinCayTong: Optional[float] = None
    ghiChu: Optional[str] = None

    class Settings:
        name = "ketQuaDiemDanh"