from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from beanie import PydanticObjectId
from beanie.operators import Or, RegEx

from app.models.phienDiemDanh import PhienDiemDanh
from app.models.suKien import SuKien
from app.models.buoiSuKien import BuoiSuKien, ToaDo
from app.models.nguoiDung import NguoiDung

from app.utils.geocoding import get_coordinates


router = APIRouter(
    prefix="/api/events",
    tags=["Cấu trúc Sự kiện & Lịch trình"]
)

# =========================================================
# SCHEMAS
# =========================================================
class ThamGiaBuoiSuKienRequest(BaseModel):
    buoiSuKienId: PydanticObjectId
    nguoiDungId: PydanticObjectId

class SuKienCreate(BaseModel):
    loaiSuKien: str
    maSuKien: Optional[str] = None
    tenSuKien: str
    moTa: Optional[str] = None
    donViToChuc: Optional[str] = None


class BuoiSuKienCreate(BaseModel):

    hocKy: Optional[int] = None
    namHoc: Optional[str] = None

    nguoiPhuTrachId: PydanticObjectId

    thoiGianBatDau: datetime
    thoiGianKetThuc: datetime

    phongHoc: Optional[str] = None
    diaDiem: Optional[str] = None
    toaDo: Optional[ToaDo] = None

    banKinhGps: Optional[int] = 30
    thoiGianChoPhepTre: Optional[int] = 15

    ghiChu: Optional[str] = None


# =========================================================
# EVENT (SuKien)
# =========================================================

@router.get("/")
async def get_events(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None
):

    filters = []

    if search:
        regex = RegEx(search, "i")

        filters.append(
            Or(
                SuKien.tenSuKien == regex,
                SuKien.maSuKien == regex,
                SuKien.donViToChuc == regex
            )
        )

    query = SuKien.find(*filters).sort("-id")

    total = await query.count()

    items = await query.skip((page - 1) * limit).limit(limit).to_list()

    return {
        "data": items,
        "total": total,
        "page": page,
        "limit": limit
    }


@router.get("/{event_id}")
async def get_event(event_id: PydanticObjectId):

    event = await SuKien.get(event_id)

    if not event:
        raise HTTPException(404, "Không tìm thấy sự kiện")

    return event


@router.post("/")
async def create_event(body: SuKienCreate):

    if body.maSuKien:

        exist = await SuKien.find_one(
            SuKien.maSuKien == body.maSuKien
        )

        if exist:
            raise HTTPException(400, "Mã sự kiện đã tồn tại")

    event = SuKien(**body.model_dump())

    await event.insert()

    return event


@router.put("/{event_id}")
async def update_event(event_id: PydanticObjectId, body: SuKienCreate):

    event = await SuKien.get(event_id)

    if not event:
        raise HTTPException(404, "Không tìm thấy sự kiện")

    update_data = body.model_dump(exclude_unset=True)

    await event.update({"$set": update_data})

    for k, v in update_data.items():
        setattr(event, k, v)

    return event


# =========================================================
# DELETE EVENT (CASCADE)
# =========================================================

@router.delete("/{event_id}")
async def delete_event(event_id: PydanticObjectId):

    event = await SuKien.get(event_id)

    if not event:
        raise HTTPException(404, "Event không tồn tại")

    # Lấy toàn bộ buổi của sự kiện
    sessions = await BuoiSuKien.find(
        BuoiSuKien.suKienId == event_id
    ).to_list()

    session_ids = [s.id for s in sessions]

    # Xóa toàn bộ phiên điểm danh của các buổi
    if session_ids:
        await PhienDiemDanh.find(
            PhienDiemDanh.buoiSuKienId.in_(session_ids)
        ).delete()

    # Xóa toàn bộ buổi
    await BuoiSuKien.find(
        BuoiSuKien.suKienId == event_id
    ).delete()

    # Xóa sự kiện
    await event.delete()

    return {
        "message": "Đã xóa sự kiện, buổi và toàn bộ phiên điểm danh liên quan"
    }

# =========================================================
# CANCEL EVENT
# =========================================================

@router.put("/{event_id}/cancel")
async def cancel_event(event_id: PydanticObjectId):

    event = await SuKien.get(event_id)

    if not event:
        raise HTTPException(404, "Không tìm thấy sự kiện")

    if event.trangThai == "daHuy":
        raise HTTPException(400, "Sự kiện đã bị hủy trước đó")

    await event.update({
        "$set": {
            "trangThai": "daHuy"
        }
    })

    event.trangThai = "daHuy"

    return {
        "message": "Đã hủy sự kiện",
        "data": event
    }

# =========================================================
# BUOI SU KIEN
# =========================================================

# ---------------------------------------------------------
# 1. LẤY DANH SÁCH BUỔI THEO EVENT
# ---------------------------------------------------------

@router.get("/{event_id}/sessions")
async def get_sessions(event_id: PydanticObjectId):

    sessions = await BuoiSuKien.find(
        BuoiSuKien.suKienId == event_id
    ).sort(+BuoiSuKien.thoiGianBatDau).to_list()

    return {"data": sessions}


# ---------------------------------------------------------
# 2. TẠO BUỔI
# ---------------------------------------------------------

@router.post("/{event_id}/sessions")
async def create_session(
    event_id: PydanticObjectId,
    body: BuoiSuKienCreate
):

    if body.thoiGianBatDau >= body.thoiGianKetThuc:
        raise HTTPException(400, "Thời gian không hợp lệ")

    event = await SuKien.get(event_id)

    if not event:
        raise HTTPException(404, "Sự kiện không tồn tại")

    manager = await NguoiDung.get(body.nguoiPhuTrachId)

    if not manager:
        raise HTTPException(400, "Người phụ trách không tồn tại")

    toa_do = body.toaDo

    if not toa_do and body.diaDiem:
        toa_do = await get_coordinates(body.diaDiem)

    session = BuoiSuKien(

        suKienId=event_id,

        hocKy=body.hocKy,
        namHoc=body.namHoc,
        nguoiPhuTrachId=body.nguoiPhuTrachId,

        thoiGianBatDau=body.thoiGianBatDau,
        thoiGianKetThuc=body.thoiGianKetThuc,

        phongHoc=body.phongHoc,
        toaDo=toa_do,

        banKinhGps=body.banKinhGps,
        thoiGianChoPhepTre=body.thoiGianChoPhepTre,

        ghiChu=body.ghiChu,

        danhSachSinhVienId=[],
        trangThai="hoatDong"
    )

    await session.insert()

    return session


# ---------------------------------------------------------
# 9. LẤY BUỔI MÀ USER THAM GIA
# ---------------------------------------------------------

@router.get("/sessions/my")
async def get_my_events(nguoiDungId: str):

    user_id = PydanticObjectId(nguoiDungId)

    events = await BuoiSuKien.find(
        {"danhSachSinhVienId": user_id}
    ).sort(+BuoiSuKien.thoiGianBatDau).to_list()

    su_kien_ids = list({e.suKienId for e in events})

    su_kiens = await SuKien.find(
        {"_id": {"$in": su_kien_ids}}
    ).to_list()

    su_kien_map = {sk.id: sk for sk in su_kiens}

    result = []

    for e in events:
        sk = su_kien_map.get(e.suKienId)

        result.append({
            **e.dict(),
            "suKien": {
                "tenSuKien": sk.tenSuKien if sk else None,
                "loaiSuKien": sk.loaiSuKien if sk else None,
                "donViToChuc": sk.donViToChuc if sk else None
            }
        })

    return result

# ---------------------------------------------------------
# 3. LẤY BUỔI THEO ID
# ---------------------------------------------------------

@router.get("/sessions/{session_id}")
async def get_session(session_id: PydanticObjectId):

    session = await BuoiSuKien.get(session_id)

    if not session:
        raise HTTPException(404, "Không tìm thấy buổi")

    return session


# ---------------------------------------------------------
# 4. UPDATE BUỔI
# ---------------------------------------------------------

@router.put("/sessions/{session_id}")
async def update_session(
    session_id: PydanticObjectId,
    body: BuoiSuKienCreate
):

    session = await BuoiSuKien.get(session_id)

    if not session:
        raise HTTPException(404, "Không tìm thấy phiên")

    # kiểm tra có phiên điểm danh chưa
    phien = await PhienDiemDanh.find(
        PhienDiemDanh.buoiSuKienId == session_id
    ).first_or_none()

    if phien:
        raise HTTPException(
            400,
            "Không thể chỉnh sửa vì đã có phiên điểm danh"
        )

    if body.thoiGianBatDau >= body.thoiGianKetThuc:
        raise HTTPException(400, "Thời gian không hợp lệ")

    session.hocKy = body.hocKy
    session.namHoc = body.namHoc
    session.nguoiPhuTrachId = body.nguoiPhuTrachId

    session.thoiGianBatDau = body.thoiGianBatDau
    session.thoiGianKetThuc = body.thoiGianKetThuc

    session.phongHoc = body.phongHoc
    session.toaDo = body.toaDo
    session.ghiChu = body.ghiChu

    await session.save()

    return session


# ---------------------------------------------------------
# 5. HỦY BUỔI
# ---------------------------------------------------------

@router.put("/sessions/{session_id}/cancel")
async def cancel_session(session_id: PydanticObjectId):

    session = await BuoiSuKien.get(session_id)

    if not session:
        raise HTTPException(404, "Không tìm thấy phiên")

    if session.trangThai == "daHuy":
        raise HTTPException(400, "Phiên đã bị hủy")

    session.trangThai = "daHuy"

    await session.save()

    return {"message": "Đã hủy phiên sự kiện"}


# ---------------------------------------------------------
# 6. XÓA BUỔI
# ---------------------------------------------------------

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: PydanticObjectId):

    session = await BuoiSuKien.get(session_id)

    if not session:
        raise HTTPException(404, "Không tìm thấy buổi")

    await session.delete()

    return {"message": "Đã xóa buổi sự kiện"}


# ---------------------------------------------------------
# 7. XÓA VĨNH VIỄN
# ---------------------------------------------------------

@router.delete("/sessions/{session_id}/force")
async def delete_session_forever(session_id: PydanticObjectId):

    session = await BuoiSuKien.get(session_id)

    if not session:
        raise HTTPException(404, "Không tìm thấy phiên")

    phien = await PhienDiemDanh.find(
        PhienDiemDanh.buoiSuKienId == session_id
    ).first_or_none()

    if phien:
        raise HTTPException(
            400,
            "Phiên đã có dữ liệu điểm danh, không thể xóa"
        )

    await session.delete()

    return {"message": "Đã xóa vĩnh viễn phiên"}


# ---------------------------------------------------------
# 8. THAM GIA BUỔI
# ---------------------------------------------------------

@router.post("/sessions/join")
async def join_buoi_su_kien(data: ThamGiaBuoiSuKienRequest):

    buoi = await BuoiSuKien.get(data.buoiSuKienId)

    if not buoi:
        raise HTTPException(404, "Buổi sự kiện không tồn tại")

    if data.nguoiDungId in buoi.danhSachSinhVienId:
        return {"message": "Bạn đã tham gia buổi sự kiện này"}

    buoi.danhSachSinhVienId.append(data.nguoiDungId)

    await buoi.save()

    return {
        "message": "Tham gia buổi sự kiện thành công",
        "buoiSuKienId": str(buoi.id)
    }


