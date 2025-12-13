# app/agents/search_enrichment/tool.py
import asyncio
import hashlib
import logging
from typing import Dict, List, Any
from datetime import datetime

from langchain_core.tools import tool
from langchain_community.tools.tavily_search import TavilySearchResults
from app.core.config import config

log = logging.getLogger(__name__)


class TavilySearchTool:
    """
    Raw Tavily search tool — returns structured dict.
    Follows the exact pattern of GoogleFactCheckTool.
    """
    def __init__(self):
        self.api_key = config.TAVILY_API_KEY
        self.cache: Dict[str, dict] = {}
        self.client = TavilySearchResults(
            max_results=3,
            api_key=self.api_key,
            search_depth="advanced",
            include_answer=True,
            include_raw_content=True,
        )
        
    def _hash(self, query: str) -> str:
        return hashlib.sha256(query.encode()).hexdigest()

    async def _search(self, query: str) -> Dict[str, Any]:
        # cache_key = self._hash(query)
        # if cached := self.cache.get(cache_key):
        #     return cached

        if not self.api_key:
            result = {"status": "error", "reason": "Tavily API key missing"}
            # self.cache[cache_key] = result
            return result

        try:
            raw = await self.client.ainvoke({"query": query})
            result = self._parse(raw, query)
            # self.cache[cache_key] = result
            return result
        except Exception as e:
            log.warning(f"Tavily raw search failed: {e}")
            error_result = {"status": "error", "reason": str(e)}
            # self.cache[cache_key] = error_result
            return error_result

    def _parse(self, raw_results: Any, query: str) -> Dict[str, Any]:
        if not isinstance(raw_results, list):
            return {"status": "error", "reason": "Invalid response", "query": query}

        answer = next((r.get("content", "") for r in raw_results if r.get("title") == "Answer"), None)

        sources = []
        seen = set()
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            url = item.get("url", "")
            if not url or url in seen or "tavily.com" in url.lower():
                continue
            seen.add(url)
            sources.append({
                "title": item.get("title", "No title"),
                "url": url,
                "snippet": item.get("content", "")[:1000],
                "domain": url.split("/")[2] if "://" in url else "unknown"
            })

        text = " ".join(s["snippet"].lower() for s in sources[:3])
        

        return {
            "status": "success",
            "query": query,
            "summary": answer or "No summary available.",
            "top_sources": sources[:5],
            "total_results": len(sources),
            "retrieved_at": datetime.now().isoformat(),
        }

    @tool("tavily_search")
    async def tavily_search(self, claim: str) -> str:
        """
        Enrich a claim with current web reporting and sources.
        Input: Factual claim
        Output: Clean, LLM-readable summary with sources
        """
        query = f"fact check OR official OR reported: \"{claim}\" site:news 2025"
        result = await self._search(query)

        if result["status"] != "success":
            return f"Web search failed for: {claim}\nError: {result.get('reason', 'Unknown')}"

        sources_text = "\n".join(
            f"• {s['title']} — {s['url']}"
            for s in result["top_sources"]
        ) or "No sources found."

        return f"""
            Web Search Results for: "{claim}"

            Summary: {result['summary']}

            Sources:
            {sources_text}

            Retrieved: {result['retrieved_at']}
            """.strip()

    