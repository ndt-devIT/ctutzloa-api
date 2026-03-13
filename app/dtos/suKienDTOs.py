from pydantic import BaseModel, Field, model_validator
from typing import Optional
from datetime import datetime
from beanie import PydanticObjectId
from app.models.suKien import ToaDo

# ======================
# Base Schema (Trường chung)
# ======================
class SuKienBase(BaseModel):
    loaiSuKien: str             # lopHoc | hoiThao | hoatDong
    tenSuKien: str
    moTa: Optional[str] = None
    donViToChuc: Optional[str] = None
    diaDiem: Optional[str] = None
    
    thoiGianBatDau: datetime
    thoiGianKetThuc: datetime

    # Validate ngày tháng: Kết thúc phải sau Bắt đầu
    @model_validator(mode='after')
    def check_dates(self):
        if self.thoiGianKetThuc <= self.thoiGianBatDau:
            raise ValueError('Thời gian kết thúc phải lớn hơn thời gian bắt đầu')
        return self

# ======================
# Schema tạo mới (CREATE)
# ======================
class SuKienCreate(SuKienBase):
    maSuKien: Optional[str] = None # Có thể tự sinh hoặc nhập tay
    nguoiPhuTrachId: PydanticObjectId # Bắt buộc phải có người phụ trách
    toaDo: Optional[ToaDo] = None

# ======================
# Schema cập nhật (UPDATE) - Tất cả đều optional
# ======================
class SuKienUpdate(BaseModel):
    loaiSuKien: Optional[str] = None
    tenSuKien: Optional[str] = None
    moTa: Optional[str] = None
    maSuKien: Optional[str] = None
    donViToChuc: Optional[str] = None
    nguoiPhuTrachId: Optional[PydanticObjectId] = None
    thoiGianBatDau: Optional[datetime] = None
    thoiGianKetThuc: Optional[datetime] = None
    diaDiem: Optional[str] = None
    trangThai: Optional[str] = None
    toaDo: Optional[ToaDo] = None

    # Validate ngày tháng nếu có update cả 2
    @model_validator(mode='after')
    def check_dates_update(self):
        if self.thoiGianBatDau and self.thoiGianKetThuc:
            if self.thoiGianKetThuc <= self.thoiGianBatDau:
                raise ValueError('Thời gian kết thúc phải lớn hơn thời gian bắt đầu')
        return self

# ======================
# Schema trả về (RESPONSE)
# ======================
class SuKienResponse(SuKienBase):
    id: PydanticObjectId = Field(serialization_alias="_id")
    maSuKien: Optional[str] = None
    nguoiPhuTrachId: PydanticObjectId
    trangThai: str
    
    # Thêm trường tọa độ vào response
    toaDo: Optional[ToaDo] = None

    class Config:
        from_attributes = True