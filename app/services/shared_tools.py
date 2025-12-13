from langchain_core.tools import tool
from app.core.cache import cache_get, cache_set, cache_delete, cache_stats
from app.core.config import config

@tool("cache_query")
async def cache_query(key: str) -> str:
    """
    Query a value from the global cache. Use to check if data is cached.
    Input: cache key (e.g., "claim:XYZ")
    """
    value = cache_get(key)
    return str(value) if value else "Not found in cache"

@tool("cache_invalidate")
async def cache_invalidate(key: str) -> str:
    """
    Delete a key from global cache. Use to force refresh.
    Input: cache key
    """
    deleted = cache_delete(key)
    return "Deleted" if deleted else "Key not found"

@tool("cache_stats")
async def get_cache_stats() -> str:
    """
    Get global cache statistics. Use to monitor cache health.
    """
    return str(cache_stats())
