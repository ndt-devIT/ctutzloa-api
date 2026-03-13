from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import httpx  # Thư viện để gọi API Zalo từ Backend

# Import Models
from app.models.nguoiDung import NguoiDung
from app.models.sinhTracHoc import SinhTracHoc
from app.models.thietBiTinCay import ThietBiTinCay

# Import Security Utilities (Giả định bạn đã có các hàm này trong app.core.security)
from app.core.security import create_access_token
from passlib.context import CryptContext

router = APIRouter(prefix="/auth", tags=["Auth"])

# Cấu hình Hashing mật khẩu
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

# ==========================================
# 1. SCHEMAS (Pydantic Models)
# ==========================================

class LoginRequest(BaseModel):
    zaloAccessToken: str 
    deviceId: Optional[str] = None      # Bổ sung Device ID từ App gửi lên
    loaiThietBi: Optional[str] = "Mobile" # VD: Android, iOS

class AdminLoginRequest(BaseModel):
    tenDangNhap: str
    matKhau: str

class LoginResponse(BaseModel):
    accessToken: str
    nguoiDungId: str
    vaiTro: str
    hoTen: str
    trangThai: str           
    daDangKyKhuonMat: bool   # Lấy real-time từ DB
    avatar: Optional[str] = None
    zaloUserId: Optional[str] = None


# ==========================================
# 2. API: ZALO LOGIN (Dành cho Sinh Viên/Cán Bộ)
# ==========================================
@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest):

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://graph.zalo.me/v2.0/me",
                params={
                    "access_token": data.zaloAccessToken,
                    "fields": "id,name,picture"
                }
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=401,
                    detail="Zalo Access Token không hợp lệ hoặc đã hết hạn"
                )

            zalo_user_data = response.json()

        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Không thể kết nối với Zalo Server"
            )

    if not zalo_user_data or "id" not in zalo_user_data:
        raise HTTPException(
            status_code=401,
            detail="Zalo Access Token không hợp lệ hoặc đã hết hạn"
        )

    zalo_id = zalo_user_data["id"]
    ten_zalo = zalo_user_data["name"]

    url_avatar = None
    if "picture" in zalo_user_data and "data" in zalo_user_data["picture"]:
        url_avatar = zalo_user_data["picture"]["data"]["url"]

    nguoi_dung = await NguoiDung.find_one(
        NguoiDung.zaloUserId == zalo_id
    )

    if not nguoi_dung:
        nguoi_dung = NguoiDung(
            zaloUserId=zalo_id,
            vaiTro="sinhVien",
            hoTen=ten_zalo,
            avatar=url_avatar,
            ngayTao=datetime.utcnow()
        )
        await nguoi_dung.insert()
    else:
        nguoi_dung.avatar = url_avatar
        nguoi_dung.hoTen = ten_zalo

    if nguoi_dung.trangThai == "khoa":
        raise HTTPException(
            status_code=403,
            detail="Tài khoản đã bị khóa"
        )

    nguoi_dung.lanDangNhapCuoi = datetime.utcnow()
    await nguoi_dung.save()

    sinh_trac = await SinhTracHoc.find_one(
        SinhTracHoc.nguoiDungId == nguoi_dung.id
    )

    if not sinh_trac:
        sinh_trac = SinhTracHoc(
            nguoiDungId=nguoi_dung.id
        )
        await sinh_trac.insert()

    if data.deviceId:
        thiet_bi = await ThietBiTinCay.find_one(
            ThietBiTinCay.nguoiDungId == nguoi_dung.id,
            ThietBiTinCay.deviceId == data.deviceId
        )

        if not thiet_bi:
            thiet_bi = ThietBiTinCay(
                nguoiDungId=nguoi_dung.id,
                deviceId=data.deviceId,
                loaiThietBi=data.loaiThietBi or "Unknown",
                lanXacThucCuoi=datetime.utcnow()
            )
            await thiet_bi.insert()
        else:
            if thiet_bi.trangThai == "khoa":
                raise HTTPException(
                    status_code=403,
                    detail="Thiết bị này đã bị chặn khỏi hệ thống"
                )

            thiet_bi.lanXacThucCuoi = datetime.utcnow()
            await thiet_bi.save()

    token = create_access_token({
        "sub": str(nguoi_dung.id),
        "vaiTro": nguoi_dung.vaiTro,
        "zaloUserId": nguoi_dung.zaloUserId
    })

    return LoginResponse(
        accessToken=token,
        nguoiDungId=str(nguoi_dung.id),
        vaiTro=nguoi_dung.vaiTro,
        hoTen=nguoi_dung.hoTen,
        trangThai=nguoi_dung.trangThai,
        daDangKyKhuonMat=sinh_trac.daDangKyKhuonMat,
        avatar=nguoi_dung.avatar,
        zaloUserId=nguoi_dung.zaloUserId
    )


# ==========================================
# 3. API: ADMIN/VIÊN CHỨC LOGIN (Web App)
# ==========================================
@router.post("/admin-login", response_model=LoginResponse)
async def admin_login(data: AdminLoginRequest):
    # 1. Tìm user trong DB
    nguoi_dung = await NguoiDung.find_one(NguoiDung.tenDangNhap == data.tenDangNhap)

    # 2. Kiểm tra tồn tại và Mật khẩu
    if not nguoi_dung or not nguoi_dung.matKhauHash:
        raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu")
    
    if not verify_password(data.matKhau, nguoi_dung.matKhauHash):
        raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu")

    # 3. Kiểm tra quyền & trạng thái
    if nguoi_dung.vaiTro not in ["admin", "vienChuc"]:
        raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập trang quản trị")

    if nguoi_dung.trangThai == "khoa":
        raise HTTPException(status_code=403, detail="Tài khoản đã bị khóa")

    # 4. Cập nhật thời gian
    nguoi_dung.lanDangNhapCuoi = datetime.utcnow()
    await nguoi_dung.save()

    # 5. Lấy trạng thái sinh trắc (Admin có thể có hoặc không)
    sinh_trac = await SinhTracHoc.find_one(SinhTracHoc.nguoiDungId == nguoi_dung.id)
    da_dang_ky_khuon_mat = sinh_trac.daDangKyKhuonMat if sinh_trac else False

    # 6. Tạo Token
    token = create_access_token({
        "sub": str(nguoi_dung.id),
        "vaiTro": nguoi_dung.vaiTro,
        "tenDangNhap": nguoi_dung.tenDangNhap
    })

    return LoginResponse(
        accessToken=token,
        nguoiDungId=str(nguoi_dung.id),
        vaiTro=nguoi_dung.vaiTro,
        hoTen=nguoi_dung.hoTen,
        trangThai=nguoi_dung.trangThai,
        daDangKyKhuonMat=da_dang_ky_khuon_mat,
        avatar=nguoi_dung.avatar
    )
    
# ==========================================
# API MỚI: ZALO LOGIN (Theo chuẩn Zalo API v4)
# (Giữ nguyên API /login cũ, gọi API này cho các bản cập nhật mới)
# ==========================================
@router.post("/login/zalo-v4", response_model=LoginResponse)
async def login_zalo_v4(data: LoginRequest):
    # 1. Gọi Zalo API v4 (Truyền token qua Header)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://graph.zalo.me/v2.0/me",
                headers={
                    "access_token": data.zaloAccessToken
                },
                params={
                    "fields": "id,name,picture"
                }
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=401,
                    detail="Zalo Access Token không hợp lệ hoặc đã hết hạn"
                )

            zalo_user_data = response.json()

            # Bắt lỗi logic từ Zalo (HTTP 200 nhưng json có key 'error')
            if zalo_user_data.get("error"):
                raise HTTPException(
                    status_code=401,
                    detail=f"Lỗi xác thực Zalo: {zalo_user_data.get('message')} (Mã: {zalo_user_data.get('error')})"
                )

        except httpx.RequestError:
            raise HTTPException(
                status_code=400,
                detail="Không thể kết nối với Zalo Server"
            )

    if not zalo_user_data or "id" not in zalo_user_data:
        raise HTTPException(
            status_code=401,
            detail="Không lấy được ID từ Zalo Access Token"
        )

    # 2. Xử lý thông tin người dùng
    zalo_id = str(zalo_user_data["id"])
    ten_zalo = zalo_user_data.get("name", "Người dùng Zalo")
    
    url_avatar = None
    if "picture" in zalo_user_data and "data" in zalo_user_data["picture"]:
        url_avatar = zalo_user_data["picture"]["data"].get("url")

    # 3. DB: Cập nhật hoặc thêm mới NguoiDung
    nguoi_dung = await NguoiDung.find_one(
        NguoiDung.zaloUserId == zalo_id
    )

    if not nguoi_dung:
        nguoi_dung = NguoiDung(
            zaloUserId=zalo_id,
            vaiTro="sinhVien",
            hoTen=ten_zalo,
            avatar=url_avatar,
            ngayTao=datetime.utcnow()
        )
        await nguoi_dung.insert()
    else:
        nguoi_dung.avatar = url_avatar
        nguoi_dung.hoTen = ten_zalo

    if getattr(nguoi_dung, "trangThai", "hoatDong") == "khoa":
        raise HTTPException(status_code=403, detail="Tài khoản đã bị khóa")

    nguoi_dung.lanDangNhapCuoi = datetime.utcnow()
    await nguoi_dung.save()

    # 4. DB: Kiểm tra Hồ sơ Sinh trắc học
    sinh_trac = await SinhTracHoc.find_one(
        SinhTracHoc.nguoiDungId == nguoi_dung.id
    )

    if not sinh_trac:
        sinh_trac = SinhTracHoc(
            nguoiDungId=nguoi_dung.id,
            daDangKyKhuonMat=False
        )
        await sinh_trac.insert()

    # 5. DB: Quản lý Thiết bị Tin cậy
    if data.deviceId:
        thiet_bi = await ThietBiTinCay.find_one(
            ThietBiTinCay.nguoiDungId == nguoi_dung.id,
            ThietBiTinCay.deviceId == data.deviceId
        )

        if not thiet_bi:
            thiet_bi = ThietBiTinCay(
                nguoiDungId=nguoi_dung.id,
                deviceId=data.deviceId,
                loaiThietBi=data.loaiThietBi or "Unknown",
                lanXacThucCuoi=datetime.utcnow(),
                trangThai="hoatDong"
            )
            await thiet_bi.insert()
        else:
            if getattr(thiet_bi, "trangThai", "hoatDong") == "khoa":
                raise HTTPException(status_code=403, detail="Thiết bị này đã bị chặn khỏi hệ thống")
            thiet_bi.lanXacThucCuoi = datetime.utcnow()
            await thiet_bi.save()

    # 6. Trả về Token hệ thống
    token = create_access_token({
        "sub": str(nguoi_dung.id),
        "vaiTro": nguoi_dung.vaiTro,
        "zaloUserId": nguoi_dung.zaloUserId
    })

    return LoginResponse(
        accessToken=token,
        nguoiDungId=str(nguoi_dung.id),
        vaiTro=nguoi_dung.vaiTro,
        hoTen=nguoi_dung.hoTen,
        trangThai=getattr(nguoi_dung, "trangThai", "hoatDong"),
        daDangKyKhuonMat=sinh_trac.daDangKyKhuonMat,
        avatar=nguoi_dung.avatar,
        zaloUserId=nguoi_dung.zaloUserId
    )