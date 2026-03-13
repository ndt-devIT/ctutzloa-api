from fastapi import APIRouter, HTTPException, status
from datetime import datetime, timezone
from beanie.operators import In
from app.models.ketQuaDiemDanh import KetQuaDiemDanh
from app.models.phienDiemDanh import PhienDiemDanh

from pydantic import BaseModel
from typing import Optional
from beanie import PydanticObjectId
from datetime import datetime
from app.utils.trangthaidiemdanh import tinh_trang_thai_diem_danh

class DiemDanhThuCongReq(BaseModel):
    phienDiemDanhId: PydanticObjectId
    nguoiDungId: PydanticObjectId
    trangThai: Optional[str] = None  # <--- Sửa ở đây
    ghiChu: Optional[str] = None

class XacThucReq(BaseModel):
    khuonMat: bool = False
    vanTay: bool = False
    gps: bool = False

class ViTriGpsReq(BaseModel):
    kinhDo: float
    viDo: float

class DiemDanhTuDongReq(BaseModel):
    phienDiemDanhId: PydanticObjectId
    nguoiDungId: PydanticObjectId
    xacThuc: XacThucReq
    viTriGps: Optional[ViTriGpsReq] = None
    deviceId: Optional[str] = None

router = APIRouter(prefix="/ket-qua-diem-danh", tags=["Kết Quả Điểm Danh"])

# =====================================================================
# API 1: LẤY DANH SÁCH ĐIỂM DANH THEO PHIÊN
# =====================================================================
@router.get("/phien/{phien_id}")
async def get_diem_danh_theo_phien(phien_id: PydanticObjectId):
    danh_sach = await KetQuaDiemDanh.find(
        KetQuaDiemDanh.phienDiemDanhId == phien_id
    ).to_list()
    
    return {"tongSo": len(danh_sach), "duLieu": danh_sach}

# =====================================================================
# API 2: LẤY DANH SÁCH ĐIỂM DANH THEO BUỔI SỰ KIỆN
# =====================================================================
@router.get("/buoi/{buoi_id}")
async def get_diem_danh_theo_buoi(buoi_id: PydanticObjectId):
    cac_phien = await PhienDiemDanh.find(PhienDiemDanh.buoiSuKienId == buoi_id).to_list()
    
    if not cac_phien:
        return {"tongSo": 0, "duLieu": []}
        
    phien_ids = [phien.id for phien in cac_phien]
    
    # Bước 2: Sử dụng toán tử In của Beanie
    danh_sach = await KetQuaDiemDanh.find(
        In(KetQuaDiemDanh.phienDiemDanhId, phien_ids) # <--- Tối ưu ở đây
    ).to_list()
    
    return {"tongSo": len(danh_sach), "duLieu": danh_sach}

# =====================================================================
# API 3: ĐIỂM DANH THỦ CÔNG (Giảng viên / Quản lý gọi)
# =====================================================================
@router.post("/thu-cong")
async def diem_danh_thu_cong(req: DiemDanhThuCongReq):
    # Kiểm tra xem phiên có tồn tại không
    phien = await PhienDiemDanh.get(req.phienDiemDanhId)
    if not phien:
        raise HTTPException(status_code=404, detail="Phiên điểm danh không tồn tại")

    thoi_gian_hien_tai = datetime.now()
    
    # Lấy trạng thái từ request. Nếu giảng viên không truyền, tự động tính toán.
    trang_thai_chot = req.trangThai if req.trangThai else tinh_trang_thai_diem_danh(thoi_gian_hien_tai, phien)

    # Kiểm tra xem người dùng đã điểm danh trong phiên này chưa (để Upsert)
    ket_qua = await KetQuaDiemDanh.find_one(
        KetQuaDiemDanh.phienDiemDanhId == req.phienDiemDanhId,
        KetQuaDiemDanh.nguoiDungId == req.nguoiDungId
    )

    if ket_qua:
        # Cập nhật kết quả hiện tại
        ket_qua.trangThai = trang_thai_chot
        ket_qua.ghiChu = req.ghiChu
        ket_qua.thoiGianDiemDanh = thoi_gian_hien_tai
        await ket_qua.save()
        return {"message": "Cập nhật điểm danh thành công", "duLieu": ket_qua}
    else:
        # Tạo mới kết quả với xác thực thủ công
        xac_thuc_fake = {"khuonMat": False, "vanTay": False, "gps": False}
        ket_qua_moi = KetQuaDiemDanh(
            phienDiemDanhId=req.phienDiemDanhId,
            nguoiDungId=req.nguoiDungId,
            thoiGianDiemDanh=thoi_gian_hien_tai,
            trangThai=trang_thai_chot,
            xacThuc=xac_thuc_fake,
            ghiChu=req.ghiChu or "Điểm danh thủ công"
        )
        await ket_qua_moi.insert()
        return {"message": "Điểm danh thủ công thành công", "duLieu": ket_qua_moi}


# =====================================================================
# API 4: ĐIỂM DANH TỰ ĐỘNG (Dành cho App Mobile/Sinh viên gọi)
# =====================================================================
@router.post("/tu-dong")
async def diem_danh_tu_dong(req: DiemDanhTuDongReq):
    phien = await PhienDiemDanh.get(req.phienDiemDanhId)
    if not phien:
        raise HTTPException(status_code=404, detail="Phiên điểm danh không tồn tại")
        
    thoi_gian_hien_tai = datetime.now()
    
    # 1. Kiểm tra trạng thái và thời gian của phiên (Validations)
    if phien.trangThai != "dangMo" or thoi_gian_hien_tai > phien.thoiGianDong or thoi_gian_hien_tai < phien.thoiGianMo:
        raise HTTPException(status_code=400, detail="Phiên điểm danh đã đóng hoặc chưa mở")

    # 2. Kiểm tra điều kiện bắt buộc (Khuôn mặt, vân tay, gps)
    if phien.batBuocKhuonMat and not req.xacThuc.khuonMat:
         raise HTTPException(status_code=400, detail="Yêu cầu xác thực khuôn mặt")
    if phien.batBuocVanTay and not req.xacThuc.vanTay:
         raise HTTPException(status_code=400, detail="Yêu cầu xác thực vân tay")
    if phien.batBuocGps and not req.xacThuc.gps:
         raise HTTPException(status_code=400, detail="Yêu cầu xác thực GPS")

    # 3. Sử dụng hàm tiện ích để lấy trạng thái (Có mặt / Đi trễ)
    trang_thai = tinh_trang_thai_diem_danh(thoi_gian_hien_tai, phien)

    # 4. Lưu kết quả
    ket_qua = KetQuaDiemDanh(
        phienDiemDanhId=req.phienDiemDanhId,
        nguoiDungId=req.nguoiDungId,
        thoiGianDiemDanh=thoi_gian_hien_tai,
        trangThai=trang_thai,
        xacThuc=req.xacThuc.model_dump(),
        viTriGps=req.viTriGps.model_dump() if req.viTriGps else None,
        deviceId=req.deviceId
    )
    
    await ket_qua.insert()
    return {"message": "Điểm danh thành công", "trangThai": trang_thai, "duLieu": ket_qua}