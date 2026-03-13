import asyncio
from datetime import datetime
from app.models.phienDiemDanh import PhienDiemDanh

async def auto_update_session_status():
    """Vòng lặp chạy ngầm để cập nhật trạng thái phiên điểm danh mỗi phút"""
    while True:
        try:
            # Lấy giờ hiện tại (Đảm bảo đồng bộ với múi giờ lưu trong DB)
            # Nếu lưu UTC thì dùng datetime.utcnow(), nếu lưu giờ VN thì dùng datetime.now()
            now = datetime.now() 

            # Tìm tất cả các phiên chưa đóng (An toàn hơn bằng cách dùng find)
            sessions_to_check = await PhienDiemDanh.find(
                PhienDiemDanh.trangThai != "daDong"
            ).to_list()

            for session in sessions_to_check:
                # 1. Kiểm tra an toàn xem field có tồn tại không
                current_status = getattr(session, "trangThai", "chuaMo")
                
                # 2. Tính thời gian đóng tuyệt đối
                absolute_close_time = session.thoiGianChoPhepTre if session.thoiGianChoPhepTre else session.thoiGianDong
                
                # Logic cập nhật
                new_status = None

                # Kịch bản: Đã qua thời hạn cuối cùng
                if now >= absolute_close_time:
                    if current_status != "daDong":
                        new_status = "daDong"
                
                # Kịch bản: Đang trong khung giờ mở (thoiGianMo <= now < absolute_close)
                elif session.thoiGianMo <= now < absolute_close_time:
                    if current_status != "dangMo":
                        new_status = "dangMo"
                
                # Kịch bản: Chưa đến giờ mở
                elif now < session.thoiGianMo:
                    if current_status != "chuaMo":
                        new_status = "chuaMo"

                # Thực hiện lưu nếu có thay đổi trạng thái
                if new_status:
                    session.trangThai = new_status
                    await session.save()
                    print(f"[Auto-Task] Update ID {session.id}: {current_status} -> {new_status}")
                        
        except Exception as e:
            # In ra chi tiết lỗi để debug (ví dụ: in cả traceback)
            print(f"[Auto-Task] Lỗi: {str(e)}")
        
        await asyncio.sleep(60)