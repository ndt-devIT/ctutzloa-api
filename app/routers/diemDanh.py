import math
from fastapi import APIRouter, HTTPException, Body, Query
from typing import List, Optional
from datetime import datetime, timezone
from beanie import PydanticObjectId
from pydantic import BaseModel, model_validator

# --- IMPORT MODELS TỪ CÁC FILE RIÊNG ---
from app.models.phienDiemDanh import PhienDiemDanh
from app.models.ketQuaDiemDanh import KetQuaDiemDanh, XacThuc, ViTriGps
from app.models.khieuNaiDiemDanh import KhieuNaiDiemDanh
from app.models.buoiSuKien import BuoiSuKien, ToaDo

router = APIRouter(prefix="/api/attendance", tags=["Nghiệp vụ Điểm danh"])

# ============================================================
# HÀM HỖ TRỢ (UTILITIES)
# ============================================================

def get_distance_meters(pos1: ViTriGps, pos2: ToaDo) -> float:
    """Tính khoảng cách Haversine giữa 2 tọa độ (Mét)"""
    R = 6371000 
    phi1, phi2 = math.radians(pos1.viDo), math.radians(pos2.viDo)
    d_phi = math.radians(pos2.viDo - pos1.viDo)
    d_lambda = math.radians(pos2.kinhDo - pos1.kinhDo)
    
    a = math.sin(d_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(d_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# ============================================================
# SCHEMAS CHO REQUEST (DTOs)
# ============================================================

class SessionCreate(BaseModel):
    buoiSuKienId: PydanticObjectId
    thoiGianMo: datetime
    thoiGianDong: datetime
    thoiGianChoPhepTre: Optional[datetime] = None
    batBuocKhuonMat: bool = False
    batBuocVanTay: bool = False
    batBuocGps: bool = False
    banKinhGps: int = 50 

    @model_validator(mode='after')
    def validate_times(self) -> 'SessionCreate':
        # 1. Thời gian mở vẫn phải trước thời gian đóng (giờ chuẩn)
        if self.thoiGianMo >= self.thoiGianDong:
            raise ValueError("Thời gian mở phải trước thời gian kết thúc điểm danh chuẩn.")
        
        # 2. Thời gian trễ (nếu có) phải SAU hoặc BẰNG thời gian đóng
        if self.thoiGianChoPhepTre:
            if self.thoiGianChoPhepTre < self.thoiGianDong:
                raise ValueError("Thời gian cho phép trễ phải bằng hoặc muộn hơn thời gian đóng chuẩn.")
        
        return self

class CheckInRequest(BaseModel):
    phienDiemDanhId: PydanticObjectId
    nguoiDungId: PydanticObjectId
    viTriGps: Optional[ViTriGps] = None
    xacThuc: XacThuc
    deviceId: Optional[str] = None
    doTinCayTong: Optional[float] = None

# ============================================================
# 1. API CHO GIẢNG VIÊN (QUẢN LÝ PHIÊN)
# ============================================================
@router.post("/sessions/open")
async def open_session(data: SessionCreate):
    """Mở cửa sổ điểm danh cho một buổi học cụ thể"""
    
    now = datetime.now()
    
    # Xác định thời điểm đóng cửa form TUYỆT ĐỐI của phiên ĐANG TẠO
    absolute_close_time = data.thoiGianChoPhepTre if data.thoiGianChoPhepTre else data.thoiGianDong

    # 1. Kiểm tra thời gian đóng tuyệt đối với thời gian hiện tại
    if absolute_close_time <= now:
         raise HTTPException(400, "Thời hạn điểm danh cuối cùng không được nằm trong quá khứ.")

    # 2. Kiểm tra buổi học có tồn tại không
    buoi_hoc = await BuoiSuKien.get(data.buoiSuKienId)
    if not buoi_hoc:
        raise HTTPException(404, "Buổi học không tồn tại")  

    # 3. Đảm bảo tuần tự giữa các phiên
    # Tìm phiên có thời gian kết thúc muộn nhất của buổi học này
    last_session = await PhienDiemDanh.find(
        PhienDiemDanh.buoiSuKienId == data.buoiSuKienId
    ).sort("-thoiGianDong").first_or_none()
    
    if last_session:
        # Lấy thời gian kết thúc tuyệt đối của phiên trước
        last_abs_close = last_session.thoiGianChoPhepTre if last_session.thoiGianChoPhepTre else last_session.thoiGianDong
        
        # LOGIC MỚI: 
        # Nếu phiên trước CHƯA ĐÓNG (dangMo/chuaMo), thời gian mở phiên mới phải SAU thời gian đóng cũ ( > )
        # Nếu phiên trước ĐÃ ĐÓNG (daDong), thời gian mở phiên mới có thể BẰNG thời gian đóng cũ ( >= )
        
        if last_session.trangThai != "daDong":
            # Nếu phiên cũ vẫn đang mở/chờ mở, không được phép trùng lặp dù chỉ 1 giây
            if data.thoiGianMo < last_abs_close:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Phiên trước đang hoạt động. Vui lòng chọn thời gian bắt đầu sau {last_abs_close.strftime('%H:%M %d/%m/%Y')}."
                )
        else:
            # Nếu phiên cũ đã đóng, cho phép bắt đầu NGAY KHI phiên cũ vừa kết thúc (Cho phép dấu =)
            if data.thoiGianMo < last_abs_close:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Thời gian mở không được sớm hơn thời gian kết thúc của phiên đã đóng ({last_abs_close.strftime('%H:%M %d/%m/%Y')})."
                )

        # (Tùy chọn): Dọn dẹp trạng thái nếu thời gian thực tế đã trôi qua
        if last_session.trangThai != "daDong" and last_abs_close <= now:
            last_session.trangThai = "daDong"
            await last_session.save()
    
    # 4. Gán trạng thái ban đầu dựa trên thời gian thực tế
    # Nếu thời gian mở là tương lai -> chuaMo, nếu đã đến giờ -> dangMo
    initial_status = "chuaMo"
    if data.thoiGianMo <= now < absolute_close_time:
        initial_status = "dangMo"

    # 5. Lưu vào Database
    session_dict = data.model_dump()
    session_dict["trangThai"] = initial_status
    
    new_session = PhienDiemDanh(**session_dict)
    await new_session.insert()
    
    return {
        "message": f"Đã tạo phiên điểm danh (Trạng thái: {initial_status})", 
        "session_id": str(new_session.id)
    }

@router.patch("/sessions/{session_id}/close")
async def close_session(session_id: PydanticObjectId):
    """Đóng phiên điểm danh (Kết thúc thời gian nhận check-in)"""
    session = await PhienDiemDanh.get(session_id)
    if not session:
        raise HTTPException(404, "Không tìm thấy phiên")
    
    session.trangThai = "daDong"
    await session.save()
    return {"message": "Phiên điểm danh đã đóng"}

@router.get("/sessions/buoi/{buoi_id}")
async def get_sessions_by_buoi(buoi_id: PydanticObjectId):
    """Lấy danh sách tất cả các phiên điểm danh thuộc một buổi học"""
    # 1. Kiểm tra buổi học có tồn tại không
    buoi_hoc = await BuoiSuKien.get(buoi_id)
    if not buoi_hoc:
        raise HTTPException(404, "Không tìm thấy buổi học")

    # 2. Tìm tất cả các phiên và sắp xếp theo thời gian mở giảm dần (mới nhất lên đầu)
    sessions = await PhienDiemDanh.find(
        PhienDiemDanh.buoiSuKienId == buoi_id
    ).sort("-thoiGianMo").to_list()

    return {
        "data": sessions,
        "total": len(sessions)
    }
# ============================================================
# 2. API CHO SINH VIÊN (CHECK-IN QUA ZALO)
# ============================================================

@router.post("/check-in")
async def submit_attendance(req: CheckInRequest):
    """Xử lý yêu cầu điểm danh của sinh viên"""
    now = datetime.utcnow()

    # 1. Lấy và kiểm tra tính hợp lệ của phiên
    session = await PhienDiemDanh.get(req.phienDiemDanhId)
    if not session or session.trangThai == "daDong" or now > session.thoiGianDong:
        raise HTTPException(400, "Phiên điểm danh không tồn tại hoặc đã kết thúc")

    # 2. Chống điểm danh lặp lại
    existed = await KetQuaDiemDanh.find_one(
        KetQuaDiemDanh.phienDiemDanhId == req.phienDiemDanhId,
        KetQuaDiemDanh.nguoiDungId == req.nguoiDungId
    )
    if existed:
        raise HTTPException(400, f"Bạn đã điểm danh lúc {existed.thoiGianDiemDanh}")

    # 3. Đối soát GPS (Nếu yêu cầu)
    if session.batBuocGps:
        if not req.viTriGps:
            raise HTTPException(400, "Yêu cầu cung cấp vị trí GPS")
        
        buoi_hoc = await BuoiSuKien.get(session.buoiSuKienId)
        if buoi_hoc and buoi_hoc.toaDo:
            distance = get_distance_meters(req.viTriGps, buoi_hoc.toaDo)
            if distance > session.banKinhGps:
                raise HTTPException(400, f"Vị trí không hợp lệ (Cách xa {int(distance)}m)")

    # 4. Xác định trạng thái (Có mặt / Trễ)
    status = "coMat"
    if session.thoiGianChoPhepTre and now > session.thoiGianChoPhepTre:
        status = "tre"

    # 5. Ghi nhận kết quả
    # Lưu ý: thoiGianDiemDanh sẽ tự sinh nhờ Field(default_factory=datetime.utcnow) trong model
    new_result = KetQuaDiemDanh(
        phienDiemDanhId=req.phienDiemDanhId,
        nguoiDungId=req.nguoiDungId,
        trangThai=status,
        xacThuc=req.xacThuc,
        viTriGps=req.viTriGps,
        deviceId=req.deviceId,
        doTinCayTong=req.doTinCayTong
    )
    await new_result.insert()
    
    return {
        "message": "Điểm danh thành công",
        "trangThai": status,
        "thoiGian": new_result.thoiGianDiemDanh
    }

# ============================================================
# 3. KHIẾU NẠI & HẬU KIỂM
# ============================================================

@router.post("/appeals")
async def send_appeal(ket_qua_id: PydanticObjectId, nguoi_dung_id: PydanticObjectId, noi_dung: str):
    """Sinh viên nộp đơn khiếu nại (VD: máy lỗi, nhận diện sai)"""
    appeal = KhieuNaiDiemDanh(
        ketQuaDiemDanhId=ket_qua_id,
        nguoiDungId=nguoi_dung_id,
        noiDung=noi_dung
    )
    await appeal.insert()
    return {"message": "Khiếu nại của bạn đã được gửi thành công"}

@router.patch("/appeals/{appeal_id}/resolve")
async def resolve_appeal(
    appeal_id: PydanticObjectId, 
    status: str = Body(..., embed=True), # chapNhan | tuChoi
    admin_id: PydanticObjectId = Body(..., embed=True)
):
    """Admin hoặc Giảng viên duyệt đơn khiếu nại"""
    appeal = await KhieuNaiDiemDanh.get(appeal_id)
    if not appeal:
        raise HTTPException(404, "Không tìm thấy khiếu nại")

    appeal.trangThai = status
    appeal.nguoiXuLyId = admin_id
    appeal.thoiGianXuLy = datetime.utcnow()
    await appeal.save()

    # Đồng bộ kết quả điểm danh nếu khiếu nại được chấp nhận
    if status == "chapNhan":
        kq = await KetQuaDiemDanh.get(appeal.ketQuaDiemDanhId)
        if kq:
            kq.trangThai = "coMat"
            kq.ghiChu = f"Duyệt bởi Admin {admin_id}"
            await kq.save()

    return {"message": f"Đã cập nhật trạng thái khiếu nại: {status}"}

@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: PydanticObjectId,
    force: bool = Query(False, description="Bắt buộc xóa ngay cả khi đã có người điểm danh")
):
    """Xóa một phiên điểm danh. Yêu cầu xác nhận (force=true) nếu đã có dữ liệu điểm danh."""
    
    # 1. Kiểm tra xem phiên có tồn tại không
    session = await PhienDiemDanh.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên điểm danh")
    
    # 2. Đếm số lượng người đã điểm danh trong phiên này
    attendance_count = await KetQuaDiemDanh.find(
        KetQuaDiemDanh.phienDiemDanhId == session_id
    ).count()
    
    # 3. Nếu có người điểm danh và chưa có cờ xác nhận (force=False) -> Yêu cầu xác nhận
    if attendance_count > 0 and not force:
        raise HTTPException(
            status_code=400, 
            detail={
                "code": "REQUIRE_CONFIRMATION",
                "message": f"Phiên này đã có {attendance_count} lượt điểm danh. Bạn có chắc chắn muốn xóa toàn bộ dữ liệu không?"
            }
        )
        
    # 4. Nếu force=True hoặc chưa có ai điểm danh -> Tiến hành xóa
    # Xóa các kết quả điểm danh thuộc phiên
    if attendance_count > 0:
        await KetQuaDiemDanh.find(KetQuaDiemDanh.phienDiemDanhId == session_id).delete()
        
    # Tiến hành xóa phiên
    await session.delete()
    
    return {"message": "Đã xóa phiên điểm danh và các dữ liệu liên quan thành công"}