import httpx
from typing import Optional, Tuple
from app.models.buoiSuKien import ToaDo

async def get_coordinates(address: str) -> Optional[ToaDo]:
    """
    Gọi API Nominatim của OpenStreetMap để lấy tọa độ từ địa chỉ.
    """
    if not address:
        return None
        
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": address,
        "format": "json",
        "limit": 1,
        "addressdetails": 1
    }
    # User-Agent là bắt buộc với Nominatim
    headers = {
        "User-Agent": "MyEventApp/1.0 (contact@example.com)" 
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    result = data[0]
                    return ToaDo(
                        viDo=float(result['lat']),
                        kinhDo=float(result['lon']),
                        hienThi=result.get('display_name', '')
                    )
        except Exception as e:
            print(f"Lỗi Geocoding: {str(e)}")
            return None
    return None