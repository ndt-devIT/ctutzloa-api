import asyncio
from datetime import datetime

from app.core.database import init_db
from app.models.nguoiDung import NguoiDung
from app.core.security import hash_password


async def create_admin():
    await init_db()

    admin = await NguoiDung.find_one(
        NguoiDung.tenDangNhap == "admin"
    )

    if admin:
        print("Admin đã tồn tại")
        return

    admin = NguoiDung(
        tenDangNhap="admin",
        matKhauHash=hash_password("123456"),
        vaiTro="admin",
        hoTen="Administrator",
        trangThai="hoatDong",
        ngayTao=datetime.utcnow()
    )
    await admin.insert()
    print("Tạo admin thành công")


asyncio.run(create_admin())
