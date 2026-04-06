from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import httpx
import os
import hmac
import hashlib
import logging

# Import Models
from app.models.nguoiDung import NguoiDung
from app.models.sinhTracHoc import SinhTracHoc
from app.models.thietBiTinCay import ThietBiTinCay

# Import Security Utilities
from app.core.security import create_access_token
from passlib.context import CryptContext

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = logging.getLogger(__name__)

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
    deviceId: Optional[str] = None
    loaiThietBi: Optional[str] = "Mobile"


class AdminLoginRequest(BaseModel):
    tenDangNhap: str
    matKhau: str


class LoginResponse(BaseModel):
    accessToken: str
    nguoiDungId: str
    vaiTro: str
    hoTen: str
    trangThai: str
    daDangKyKhuonMat: bool
    avatar: Optional[str] = None
    zaloUserId: Optional[str] = None


# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================

def make_appsecret_proof(access_token: str, app_secret: str) -> str:
    return hmac.new(
        app_secret.encode("utf-8"),
        access_token.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def extract_avatar_url(zalo_user_data: Dict[str, Any]) -> Optional[str]:
    return (
        zalo_user_data.get("picture", {})
        .get("data", {})
        .get("url")
    )


async def get_zalo_profile(zalo_access_token: str) -> Dict[str, Any]:
    app_secret = os.getenv("ZALO_APP_SECRET")

    if not app_secret:
        logger.error("Thiếu biến môi trường ZALO_APP_SECRET")
        raise HTTPException(
            status_code=500,
            detail="Thiếu cấu hình ZALO_APP_SECRET trên server"
        )

    appsecret_proof = make_appsecret_proof(zalo_access_token, app_secret)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://graph.zalo.me/v2.0/me",
                headers={
                    "access_token": zalo_access_token,
                    "appsecret_proof": appsecret_proof
                },
                params={
                    "fields": "id,name,picture"
                }
            )
    except httpx.RequestError as e:
        logger.exception("Không thể kết nối tới Zalo Server")
        raise HTTPException(
            status_code=400,
            detail=f"Không thể kết nối tới Zalo Server: {str(e)}"
        )

    response_text = response.text
    logger.info("Zalo response status=%s body=%s", response.status_code, response_text)

    try:
        zalo_user_data = response.json()
    except Exception:
        logger.exception("Zalo trả về dữ liệu không phải JSON")
        raise HTTPException(
            status_code=502,
            detail="Zalo trả về dữ liệu không hợp lệ"
        )

    if response.status_code != 200:
        logger.warning("Zalo xác thực thất bại: %s", zalo_user_data)
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Zalo Access Token không hợp lệ hoặc đã hết hạn",
                "zalo_response": zalo_user_data
            }
        )

    # Một số trường hợp API trả 200 nhưng vẫn có error/message trong body
    if zalo_user_data.get("error") not in [0, None]:
        logger.warning("Zalo trả lỗi logic: %s", zalo_user_data)
        raise HTTPException(
            status_code=401,
            detail={
                "message": zalo_user_data.get("message", "Lỗi xác thực Zalo"),
                "zalo_response": zalo_user_data
            }
        )

    if "id" not in zalo_user_data:
        logger.warning("Không lấy được id từ Zalo response: %s", zalo_user_data)
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Không lấy được ID từ Zalo Access Token",
                "zalo_response": zalo_user_data
            }
        )

    return zalo_user_data


async def handle_zalo_login(data: LoginRequest) -> LoginResponse:
    zalo_user_data = await get_zalo_profile(data.zaloAccessToken)

    zalo_id = str(zalo_user_data["id"])
    ten_zalo = zalo_user_data.get("name", "Người dùng Zalo")
    url_avatar = extract_avatar_url(zalo_user_data)

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
        nguoi_dung.hoTen = ten_zalo
        nguoi_dung.avatar = url_avatar

    if getattr(nguoi_dung, "trangThai", "hoatDong") == "khoa":
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
            nguoiDungId=nguoi_dung.id,
            daDangKyKhuonMat=False
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
                lanXacThucCuoi=datetime.utcnow(),
                trangThai="hoatDong"
            )
            await thiet_bi.insert()
        else:
            if getattr(thiet_bi, "trangThai", "hoatDong") == "khoa":
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
        trangThai=getattr(nguoi_dung, "trangThai", "hoatDong"),
        daDangKyKhuonMat=sinh_trac.daDangKyKhuonMat,
        avatar=nguoi_dung.avatar,
        zaloUserId=nguoi_dung.zaloUserId
    )


# ==========================================
# 3. API: ZALO LOGIN
# Giữ /login để không vỡ frontend cũ
# ==========================================

@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest):
    return await handle_zalo_login(data)


# ==========================================
# 4. API: ADMIN/VIÊN CHỨC LOGIN (Web App)
# ==========================================

@router.post("/admin-login", response_model=LoginResponse)
async def admin_login(data: AdminLoginRequest):
    nguoi_dung = await NguoiDung.find_one(
        NguoiDung.tenDangNhap == data.tenDangNhap
    )

    if not nguoi_dung or not getattr(nguoi_dung, "matKhauHash", None):
        raise HTTPException(
            status_code=401,
            detail="Sai tên đăng nhập hoặc mật khẩu"
        )

    if not verify_password(data.matKhau, nguoi_dung.matKhauHash):
        raise HTTPException(
            status_code=401,
            detail="Sai tên đăng nhập hoặc mật khẩu"
        )

    if nguoi_dung.vaiTro not in ["admin", "vienChuc"]:
        raise HTTPException(
            status_code=403,
            detail="Bạn không có quyền truy cập trang quản trị"
        )

    if getattr(nguoi_dung, "trangThai", "hoatDong") == "khoa":
        raise HTTPException(
            status_code=403,
            detail="Tài khoản đã bị khóa"
        )

    nguoi_dung.lanDangNhapCuoi = datetime.utcnow()
    await nguoi_dung.save()

    sinh_trac = await SinhTracHoc.find_one(
        SinhTracHoc.nguoiDungId == nguoi_dung.id
    )
    da_dang_ky_khuon_mat = sinh_trac.daDangKyKhuonMat if sinh_trac else False

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
        trangThai=getattr(nguoi_dung, "trangThai", "hoatDong"),
        daDangKyKhuonMat=da_dang_ky_khuon_mat,
        avatar=nguoi_dung.avatar,
        zaloUserId=getattr(nguoi_dung, "zaloUserId", None)
    )


# ==========================================
# 5. API: ZALO LOGIN V4
# Giữ route này để tương thích frontend mới
# ==========================================

@router.post("/login/zalo-v4", response_model=LoginResponse)
async def login_zalo_v4(data: LoginRequest):
    return await handle_zalo_login(data)