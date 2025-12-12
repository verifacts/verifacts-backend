from langchain_core.tools import tool
from app.core.cache import cache_get, cache_set, cache_delete, cache_stats
from app.core.config import config
from langchain_community.tools.tavily_search import TavilySearchResults

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

@tool("tavily_search")
async def tavily_search(query: str, max_results: int = 5) -> str:
    """
    Advanced AI-powered web search. Use for complex research or when standard search lacks context.
    Returns summarized results with sources.
    """
    tool = TavilySearchResults(
        max_results=max_results,
        api_key=config.TAVILY_API_KEY,  # Add to .env
        search_depth = "advanced",
        include_answer = True,
        include_raw_content =True
    )
    results = await tool.ainvoke(query)
    return str(results)  # Or parse to dict

