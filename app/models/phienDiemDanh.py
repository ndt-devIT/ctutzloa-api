from typing import Optional
from beanie import Document, PydanticObjectId
from datetime import datetime
from pydantic import Field
import random
import string


def generate_code():
    today = datetime.now().strftime("%d%m%y")
    rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"{today}{rand}"


class PhienDiemDanh(Document):

    code: str = Field(default_factory=generate_code)

    buoiSuKienId: PydanticObjectId

    thoiGianMo: datetime
    thoiGianDong: datetime

    thoiGianChoPhepTre: Optional[datetime] = None

    batBuocKhuonMat: bool = False
    batBuocVanTay: bool = False
    batBuocGps: bool = False
    banKinhGps: int = 0

    trangThai: str = "chuaMo"

    class Settings:
        name = "phienDiemDanh"