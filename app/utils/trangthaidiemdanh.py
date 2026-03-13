from datetime import datetime
from fastapi import HTTPException, status
from app.models.ketQuaDiemDanh import KetQuaDiemDanh
from app.models.phienDiemDanh import PhienDiemDanh

def tinh_trang_thai_diem_danh(thoi_gian_diem_danh: datetime, phien: PhienDiemDanh) -> str:
    """
    So sánh thời gian điểm danh thực tế với các mốc thời gian của phiên
    để trả về trạng thái tương ứng.
    """
    # 1. Kiểm tra xem điểm danh có nằm ngoài khoảng thời gian mở/đóng không
    if thoi_gian_diem_danh < phien.thoiGianMo:  # <-- SỬA DẤU TẠI ĐÂY: Nhỏ hơn giờ mở
         raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST, 
             detail="Phiên điểm danh chưa đến giờ mở."
         )
         
    if thoi_gian_diem_danh > phien.thoiGianDong: # <-- SỬA DẤU TẠI ĐÂY: Lớn hơn giờ đóng
         raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST, 
             detail="Phiên điểm danh đã đóng."
         )

    # 2. Xét trạng thái đi trễ (nếu phiên có cấu hình mốc thời gian trễ)
    if phien.thoiGianChoPhepTre:
        if thoi_gian_diem_danh <= phien.thoiGianChoPhepTre:
            return "coMat"
        else:
            return "diTre"
            
    # 3. Nếu không có cấu hình mốc đi trễ, cứ điểm danh trong giờ là có mặt
    return "coMat"