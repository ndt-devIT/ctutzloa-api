from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from app.core.config import MONGO_URI, DB_NAME

from app.models.nguoiDung import NguoiDung
from app.models.suKien import SuKien
from app.models.chiTietSuKien import ChiTietSuKien
from app.models.buoiSuKien import BuoiSuKien
from app.models.phienDiemDanh import PhienDiemDanh
from app.models.sinhTracHoc import SinhTracHoc
from app.models.thietBiTinCay import ThietBiTinCay
from app.models.ketQuaDiemDanh import KetQuaDiemDanh
from app.models.khieuNaiDiemDanh import KhieuNaiDiemDanh
from app.models.thongBao import ThongBao
from app.models.auditLog import AuditLog
from app.models.zaloPKCE import ZaloPKCE
from app.models.zaloToken import ZaloToken
from app.models.zaloFollowers import ZaloFollower


class Database:
    client: AsyncIOMotorClient = None


db = Database()


async def init_db():
    """
    Khởi tạo kết nối MongoDB + Beanie ODM
    Gọi duy nhất 1 lần khi startup FastAPI
    """
    db.client = AsyncIOMotorClient(MONGO_URI)

    await init_beanie(
        database=db.client[DB_NAME],
        document_models=[
            NguoiDung,
            SuKien,
            BuoiSuKien,
            PhienDiemDanh,
            SinhTracHoc,
            ThietBiTinCay,
            KetQuaDiemDanh,
            KhieuNaiDiemDanh,
            ThongBao,
            AuditLog,
            ZaloPKCE,
            ZaloToken,
            ZaloFollower
        ],
    )


async def close_db():
    """
    Đóng kết nối MongoDB khi shutdown app
    """
    if db.client:
        db.client.close()
