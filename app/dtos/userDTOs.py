from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from beanie import PydanticObjectId
from pydantic import BaseModel

# Base schema cho các trường chung
class UserBase(BaseModel):
    hoTen: str
    vaiTro: str  # sinhVien, giangVien, admin
    email: Optional[EmailStr] = None
    soDienThoai: Optional[str] = None
    avatar: Optional[str] = None
    
    # Sinh viên
    maSinhVien: Optional[str] = None
    lop: Optional[str] = None
    khoa: Optional[str] = None
    nganh: Optional[str] = None
    namNhapHoc: Optional[int] = None

    # Giảng viên
    maVienChuc: Optional[str] = None
    hocVi: Optional[str] = None
    
    # Trạng thái
    trangThai: Optional[str] = "hoatDong"

# Schema khi TẠO người dùng mới
class UserCreate(UserBase):
    # Chỉ bắt buộc với Admin, nhưng để optional ở đây để handle logic trong code
    tenDangNhap: Optional[str] = None 
    matKhau: Optional[str] = None # Mật khẩu dạng text (sẽ được hash)

# Schema khi CẬP NHẬT người dùng (Tất cả đều optional)
class UserUpdate(BaseModel):
    hoTen: Optional[str] = None
    vaiTro: Optional[str] = None
    email: Optional[EmailStr] = None
    soDienThoai: Optional[str] = None
    lop: Optional[str] = None
    khoa: Optional[str] = None
    nganh: Optional[str] = None
    namNhapHoc: Optional[int] = None
    hocVi: Optional[str] = None
    trangThai: Optional[str] = None
    matKhau: Optional[str] = None   

# Schema để trả về Client (ẩn mật khẩu hash)
class UserResponse(UserBase):
    id: PydanticObjectId = Field(serialization_alias="_id")
    tenDangNhap: Optional[str] = None
    ngayTao: datetime
    lanDangNhapCuoi: Optional[datetime] = None

    class Config:
        from_attributes = True
        

class ChangeStatusReq(BaseModel):
    trangThai: str  # "hoatDong" | "khoa"
    
class ImportItem(BaseModel):
    hoTen: str
    maVienChuc: str
    email: str
    hocVi: str | None = None
    soDienThoai: str | None = None