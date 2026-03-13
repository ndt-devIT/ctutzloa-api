from beanie import Document
from typing import Optional

class SuKien(Document):
    loaiSuKien: str
    maSuKien: Optional[str] = None
    tenSuKien: str
    moTa: Optional[str] = None
    donViToChuc: Optional[str] = None

    trangThai: str = "hoatDong"

    class Settings:
        name = "suKien"