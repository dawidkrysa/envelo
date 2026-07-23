import httpx
from config import API_GATEWAY_URL


async def get_health() -> bool:
    try:
        async with httpx.AsyncClient(base_url=API_GATEWAY_URL, timeout=5) as client:
            response = await client.get("/health")
        return response.status_code == 200
    except httpx.HTTPError:
        return False
