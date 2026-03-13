from fastapi import APIRouter, Depends
from app.core.admin_auth import verify_admin_token
from app.models.nguoiDung import NguoiDung

router = APIRouter(
    prefix="/admin/users",
    tags=["Admin - User"]
)


@router.get("/me")
async def get_me(admin: NguoiDung = Depends(verify_admin_token)):
    return {
        "id": str(admin.id),
        "hoTen": admin.hoTen,
        "vaiTro": admin.vaiTro
    }
