import logging
from typing import Any, Optional

from redis import Redis
from langchain_core.globals import set_llm_cache 
from langchain_community.cache import RedisCache, RedisSemanticCache
from langchain_openai import OpenAIEmbeddings

from app.core.config import config

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

redis_client = Redis.from_url(config.REDIS_URL)


def init_global_cache(semantic: bool=True) -> None:
    """Initializes a global Redis cache for LangChain operations."""
    global redis_client
    if not redis_client:
        logger.warning("Redis client is not configured; caching will be disabled.")
        return
    
    if semantic:
        logger.info("Initializing Redis Semantic Cache with Google Embeddings.")
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small"
        )
        cache = RedisSemanticCache(
            redis_client=redis_client,
            embedding_function=embeddings,
            index_name=config.REDIS_SEMANTIC_INDEX or "langchain_semantic_cache",
            score_threshold=0.85
        )
    else:
        logger.info("Initializing standard Redis Cache.")
        cache = RedisCache(redis_client=redis_client)
    
    from langchain_core.globals import set_llm_cache
    set_llm_cache(cache)
    logger.info("Global Redis cache initialized successfully.")
    
    try:
        # Test the connection
        redis_client.ping()
        logger.info("Successfully connected to Redis server.")
    except Exception as e:
        logger.error(f"Failed to connect to Redis server: {e}")
        redis_client = None
        
        
def cache_get(key:str) -> Optional[Any]:
    """Retrieve a value from the Redis cache by key."""
    global redis_client
    if not redis_client:
        logger.warning("Redis client is not configured; cannot get cache.")
        return None
    try:
        value = redis_client.get(key)
        if value is not None:
            logger.info(f"Cache hit for key: {key}")
        else:
            logger.info(f"Cache miss for key: {key}")
        return value
    except Exception as e:
        logger.error(f"Error retrieving key {key} from cache: {e}")
        return None
    
def cache_set(key:str, value:Any, ttl:int=config.CACHE_TTL) -> None:
    """Set a value in the Redis cache with an optional TTL."""
    global redis_client
    if not redis_client:
        logger.warning("Redis client is not configured; cannot set cache.")
        return
    try:
        redis_client.set(name=key, value=value, ex=ttl)
        logger.info(f"Cache set for key: {key} with TTL: {ttl} seconds")
    except Exception as e:
        logger.error(f"Error setting key {key} in cache: {e}")
        
def cache_delete(key:str) -> None:
    """Delete a value from the Redis cache by key."""
    global redis_client
    if not redis_client:
        logger.warning("Redis client is not configured; cannot delete cache.")
        return
    try:
        redis_client.delete(key)
        logger.info(f"Cache deleted for key: {key}")
    except Exception as e:
        logger.error(f"Error deleting key {key} from cache: {e}")
        

def cache_stats() -> Optional[dict]:
    """Retrieve Redis cache statistics."""
    global redis_client
    if not redis_client:
        logger.warning("Redis client is not configured; cannot get stats.")
        return None
    try:
        info = redis_client.info()
        stats = {
            "used_memory_human": info.get("used_memory_human"),
            "keyspace_hits": info.get("keyspace_hits"),
            "keyspace_misses": info.get("keyspace_misses"),
            "connected_clients": info.get("connected_clients"),
            "uptime_in_seconds": info.get("uptime_in_seconds"),
        }
        logger.info(f"Redis cache stats: {stats}")
        return stats
    except Exception as e:
        logger.error(f"Error retrieving Redis stats: {e}")
        return None
    
# Usage Example
# init_global_cache(semantic=True)
# #ping

# if __name__ == "__main__":
#     if not redis_client:
#         logger.warning("Redis client is not configured; skipping ping.")
        
#     if redis_client:
#         try:
#             redis_client.ping()
#             logger.info("Ping to Redis server successful.")
#         except Exception as e:
#             logger.error(f"Ping to Redis server failed: {e}")