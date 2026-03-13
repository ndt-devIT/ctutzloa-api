from beanie import Document, PydanticObjectId
from datetime import datetime

class ThietBiTinCay(Document):
    nguoiDungId: PydanticObjectId
    deviceId: str
    loaiThietBi: str
    lanXacThucCuoi: datetime
    trangThai: str = "hoatDong"

    class Settings:
        name = "thietBiTinCay"
