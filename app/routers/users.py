from datetime import datetime
from io import BytesIO
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from typing import List, Optional
from beanie import PydanticObjectId
from beanie.operators import Or
from pydantic import BaseModel
import pandas as pd

# Import models
from app.models.nguoiDung import NguoiDung 
from app.models.sinhTracHoc import SinhTracHoc         # Thêm dòng này
from app.models.thietBiTinCay import ThietBiTinCay     # Thêm dòng này
from app.models.zaloFollowers import ZaloFollower      # Thêm dòng này

from app.dtos.userDTOs import ChangeStatusReq, UserCreate, UserUpdate, UserResponse, ImportItem
from app.utils import password

router = APIRouter(prefix="/api/users", tags=["Admin - Quản lý người dùng"])

# =========================================================
# 1. LẤY DANH SÁCH NGƯỜI DÙNG (Có phân trang & lọc)
# =========================================================
@router.get("/") 
async def get_users(
    page: int = 1,
    limit: int = 10,
    vai_tro: Optional[str] = None,
    search: Optional[str] = None
):
    query = NguoiDung.find_all()

    if vai_tro:
        query = query.find(NguoiDung.vaiTro == vai_tro)

    if search:
        query = query.find(
            {
                "$or": [
                    {"hoTen": {"$regex": search, "$options": "i"}},
                    {"email": {"$regex": search, "$options": "i"}},
                    {"maSinhVien": {"$regex": search, "$options": "i"}},
                    {"maVienChuc": {"$regex": search, "$options": "i"}} 
                ]
            }
        )

    total_count = await query.count()
    skip = (page - 1) * limit
    users = await query.skip(skip).limit(limit).sort("-ngayTao").to_list()
    
    return {
        "items": users,
        "total": total_count
    }

@router.get("/zalo-followers")
async def get_zalo_followers(
    page: int = 1,
    limit: int = 10,
    search: Optional[str] = None,
    sync: Optional[str] = None
):

    query = ZaloFollower.find_all()

    if search:
        query = query.find({
            "$or": [
                {"displayName": {"$regex": search, "$options": "i"}},
                {"userIdByApp": {"$regex": search, "$options": "i"}},
            ]
        })

    total = await query.count()

    skip = (page - 1) * limit
    followers = await query.skip(skip).limit(limit).to_list()

    user_ids = [f.userIdByApp for f in followers if f.userIdByApp]

    users = await NguoiDung.find(
        {"zaloUserId": {"$in": user_ids}}
    ).to_list()

    synced_ids = {u.zaloUserId for u in users}

    results = []

    for f in followers:

        is_synced = f.userIdByApp in synced_ids

        # filter trạng thái
        if sync == "true" and not is_synced:
            continue
        if sync == "false" and is_synced:
            continue

        results.append({
            "userId": f.userId,
            "userIdByApp": f.userIdByApp,
            "displayName": f.displayName,
            "avatar": f.avatar,
            "isSynced": is_synced
        })

    return {
        "items": results,
        "total": total
    }

# =========================================================
# 2. TẠO NGƯỜI DÙNG MỚI
# =========================================================
@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user_in: UserCreate):

    user_dict = user_in.model_dump(exclude_unset=True)

    # ============================
    # TỰ ĐỘNG XÁC ĐỊNH VAI TRÒ
    # ============================

    email = user_dict.get("email")

    if email and email.lower().endswith("@ctuet.edu.vn"):
        user_dict["vaiTro"] = "vienChuc"
    elif "vaiTro" not in user_dict:
        user_dict["vaiTro"] = "sinhVien"

    # ============================
    # VALIDATION ADMIN / VIÊN CHỨC
    # ============================

    if user_dict["vaiTro"] in ["admin", "vienChuc"]:

        if not user_dict.get("tenDangNhap") or not user_dict.get("matKhau"):
            raise HTTPException(
                400,
                "Tài khoản quản trị/viên chức cần có tên đăng nhập và mật khẩu"
            )

        exist_admin = await NguoiDung.find_one(
            NguoiDung.tenDangNhap == user_dict["tenDangNhap"]
        )

        if exist_admin:
            raise HTTPException(400, "Tên đăng nhập đã tồn tại")

    # ============================
    # KIỂM TRA MÃ SINH VIÊN
    # ============================

    if user_dict["vaiTro"] == "sinhVien" and user_dict.get("maSinhVien"):

        exist_sv = await NguoiDung.find_one(
            NguoiDung.maSinhVien == user_dict["maSinhVien"]
        )

        if exist_sv:
            raise HTTPException(400, "Mã sinh viên đã tồn tại")

    # ============================
    # HASH PASSWORD
    # ============================

    if "matKhau" in user_dict and user_dict["matKhau"]:
        user_dict["matKhauHash"] = password.get_password_hash(
            user_dict.pop("matKhau")
        )

    # ============================
    # TẠO USER
    # ============================

    new_user = NguoiDung(**user_dict)
    await new_user.insert()

    # ============================
    # TẠO SINH TRẮC HỌC
    # ============================

    sinh_trac = SinhTracHoc(
        nguoiDungId=new_user.id
    )

    await sinh_trac.insert()

    return new_user

# =========================================================
# 3. LẤY CHI TIẾT 1 NGƯỜI DÙNG
# =========================================================
@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(user_id: PydanticObjectId):
    user = await NguoiDung.get(user_id)
    if not user:
        raise HTTPException(404, "Không tìm thấy người dùng")
    return user

# =========================================================
# 4. CẬP NHẬT NGƯỜI DÙNG
# =========================================================
@router.put("/{user_id}", response_model=UserResponse)
async def update_user(user_id: PydanticObjectId, user_in: UserUpdate):
    user = await NguoiDung.get(user_id)
    if not user:
        raise HTTPException(404, "Không tìm thấy người dùng")

    update_data = user_in.dict(exclude_unset=True)

    protected_fields = ["zaloUserId", "tenDangNhap", "matKhauHash", "maSinhVien", "maVienChuc"]
    for field in protected_fields:
        if field in update_data:
            update_data.pop(field)

    if "matKhau" in update_data:
        plain_password = update_data.pop("matKhau") 
        if plain_password: 
            update_data["matKhauHash"] = password.get_password_hash(plain_password) 

    await user.update({"$set": update_data})
    updated_user = await NguoiDung.get(user_id)
    return updated_user

# =========================================================
# 5. XÓA NGƯỜI DÙNG
# =========================================================
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: PydanticObjectId):
    user = await NguoiDung.get(user_id)
    if not user:
        raise HTTPException(404, "Không tìm thấy người dùng")
    
    # CASCADE DELETE: Xóa dữ liệu liên quan để tránh rác DB
    await SinhTracHoc.find(SinhTracHoc.nguoiDungId == user_id).delete()
    await ThietBiTinCay.find(ThietBiTinCay.nguoiDungId == user_id).delete()
    
    await user.delete()
    return None

# ============================================================
# 6. Chuyển trạng thái tài khoản (Active/Lock)
# ============================================================
@router.patch("/{user_id}/status", response_model=UserResponse)
async def change_user_status(user_id: PydanticObjectId, req: ChangeStatusReq):
    if req.trangThai not in ["hoatDong", "khoa"]:
        raise HTTPException(status_code=400, detail="Trạng thái không hợp lệ")

    user = await NguoiDung.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")

    user.trangThai = req.trangThai
    await user.save()
    return user

# ============================================================
# 7. EXCEL IMPORT - PREVIEW
# ============================================================
@router.post("/import/preview")
async def preview_import_vien_chuc(file: UploadFile = File(...)):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Vui lòng upload file Excel (.xlsx)")

    try:
        contents = await file.read()
        df = pd.read_excel(BytesIO(contents))
        df.columns = [str(col).strip().lower() for col in df.columns]

        valid_data = []  
        invalid_data = [] 

        for index, row in df.iterrows():
            row_idx = index + 2
            
            ma_vc = str(row.get('mã viên chức', '')).strip()
            ho_ten = str(row.get('họ tên', '')).strip()
            email = str(row.get('email', '')).strip()
            hoc_vi = str(row.get('học vị', '')).strip()
            sdt = str(row.get('số điện thoại', '')).strip()

            if not ma_vc or ma_vc == 'nan':
                invalid_data.append({"row": row_idx, "error": "Thiếu mã viên chức", "data": row.to_dict()})
                continue
            
            if not email or email == 'nan':
                invalid_data.append({"row": row_idx, "error": "Thiếu email", "data": row.to_dict()})
                continue

            exist_user = await NguoiDung.find_one(
                Or(NguoiDung.maVienChuc == ma_vc, NguoiDung.email == email)
            )

            if exist_user:
                invalid_data.append({
                    "row": row_idx, 
                    "error": f"Đã tồn tại Mã VC '{ma_vc}' hoặc Email '{email}'",
                    "data": { "hoTen": ho_ten, "maVienChuc": ma_vc, "email": email }
                })
            else:
                valid_data.append({
                    "hoTen": ho_ten,
                    "maVienChuc": ma_vc,
                    "email": email,
                    "hocVi": hoc_vi if hoc_vi != 'nan' else None,
                    "soDienThoai": sdt if sdt != 'nan' else None
                })

        return {
            "valid_count": len(valid_data),
            "invalid_count": len(invalid_data),
            "valid_data": valid_data,     
            "invalid_data": invalid_data  
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi đọc file Excel: {str(e)}")

# ============================================================
# 8. EXCEL IMPORT - EXECUTE
# ============================================================
@router.post("/import/execute")
async def execute_import_vien_chuc(data: List[ImportItem]):
    count = 0
    try:
        for item in data:
            hashed_pw = password.hash_password(item.maVienChuc) # Đồng bộ hàm hash
            
            new_vc = NguoiDung(
                hoTen=item.hoTen,
                vaiTro="vienChuc",
                maVienChuc=item.maVienChuc,
                email=item.email,
                hocVi=item.hocVi,
                soDienThoai=item.soDienThoai,
                tenDangNhap=item.maVienChuc,
                matKhauHash=hashed_pw,
                trangThai="hoatDong"
            )
            await new_vc.create()

            # TỰ ĐỘNG TẠO RECORD SINH TRẮC HỌC
            sinh_trac = SinhTracHoc(nguoiDungId=new_vc.id)
            await sinh_trac.insert()

            count += 1
            
        return {"message": "Import thành công", "count": count}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lưu dữ liệu: {str(e)}")

# ============================================================
@router.post("/sync-user/{follower_id}")
async def sync_user(follower_id: str):

    follower = await ZaloFollower.find_one(
        ZaloFollower.userId == follower_id
    )

    if not follower:
        raise HTTPException(404, "Follower không tồn tại")

    # kiểm tra đã sync chưa
    existed = await NguoiDung.find_one(
        NguoiDung.zaloUserId == follower.userIdByApp
    )

    if existed:
        return {"message": "User đã tồn tại"}

    # ==============================
    # TẠO NGƯỜI DÙNG
    # ==============================

    user = NguoiDung(
        zaloUserId=follower.userIdByApp,
        vaiTro="sinhVien",
        hoTen=follower.displayName,
        avatar=follower.avatar
    )

    await user.insert()

    # ==============================
    # TẠO SINH TRẮC HỌC
    # ==============================

    sinh_trac_hoc = SinhTracHoc(
        nguoiDungId=user.id
    )

    await sinh_trac_hoc.insert()

    # ==============================
    # CẬP NHẬT FOLLOWER
    # ==============================

    follower.isSynced = True
    follower.updatedAt = datetime.utcnow()

    await follower.save()

    return {
        "message": "Đồng bộ thành công",
        "userId": user.id
    }