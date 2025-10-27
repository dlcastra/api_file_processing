import asyncio
import json

from src.settings.config import redis


async def wait_for_cache(s3_key: str, cache_key: str, timeout: int = 30, interval: float = 0.2) -> dict | None:
    """Waits for the result to appear in the cache with timeout"""
    uuid_key = s3_key.split("_")[0]
    cache_key = f"{cache_key}:{uuid_key}"
    start_time = asyncio.get_event_loop().time()

    while (asyncio.get_event_loop().time() - start_time) < timeout:
        status_data = await redis.get(cache_key)
        if status_data:
            try:
                return json.loads(status_data)
            except json.JSONDecodeError:
                raise {"message": "Invalid data in cache"}
        await asyncio.sleep(interval)

    return None
