from beanie import Document
from typing import Optional
from datetime import datetime


class NguoiDung(Document):
    # ======================
    # Định danh chung
    # ======================
    zaloUserId: Optional[str] = None 
    vaiTro: str                     # sinhVien | vienChuc | admin
    hoTen: str
    email: Optional[str] = None
    soDienThoai: Optional[str] = None
    avatar: Optional[str] = None

    # ======================
    # Dành cho ADMIN (Web Admin)
    # ======================
    tenDangNhap: Optional[str] = None
    matKhauHash: Optional[str] = None

    # ======================
    # Sinh viên
    # ======================
    maSinhVien: Optional[str] = None
    lop: Optional[str] = None
    khoa: Optional[str] = None
    nganh: Optional[str] = None
    namNhapHoc: Optional[int] = None

    # ======================
    # Giảng viên / cán bộ
    # ======================
    maVienChuc: Optional[str] = None
    hocVi: Optional[str] = None

    # ======================
    # Trạng thái & thời gian
    # ======================
    trangThai: str = "hoatDong"     # hoatDong | khoa
    ngayTao: datetime = datetime.utcnow()
    lanDangNhapCuoi: Optional[datetime] = None

    class Settings:
        name = "nguoiDung"
        use_state_management = True
