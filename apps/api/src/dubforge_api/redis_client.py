from functools import lru_cache

import redis.asyncio as redis

from dubforge_api.config import get_settings


@lru_cache
def get_redis() -> redis.Redis:
    return redis.from_url(get_settings().redis_url, decode_responses=True)
