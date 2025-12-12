# agents/fact_checker/tool.py
import asyncio
import hashlib
import logging
from typing import Dict, List, Optional

import aiohttp
from langchain_core.tools import tool

from app.core.config import config

log = logging.getLogger(__name__)


class GoogleFactCheckTool:
    """LangChain tool that verifies claims using Google Fact Check Tools API"""

    def __init__(self, api_key: str):
        self.api_key = api_key or config.GOOGLE_FACT_CHECK_KEY
        self.base_url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
        self.cache: Dict[str, dict] = {}

    def _hash(self, claim: str) -> str:
        return hashlib.sha256(claim.lower().strip().encode()).hexdigest()

    async def _search(self, claim: str) -> dict:
        if cached := self.cache.get(self._hash(claim)):
            return cached

        if not self.api_key:
            return {"status": "error", "reason": "API key missing"}

        params = {"query": claim, "key": self.api_key, "languageCode": "en"}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(self.base_url, params=params) as resp:
                    data = await resp.json() if resp.status == 200 else {}
                    result = self._parse(data.get("claims", []), claim)
                    self.cache[self._hash(claim)] = result
                    return result
        except Exception as e:
            log.warning(f"Fact-check API error: {e}")
            return {"status": "unverified", "reason": "API error"}

    def _parse(self, claims: List[dict], original: str) -> dict:
        if not claims:
            return {
                "status": "unverified",
                "claim": original,
                "reason": "No fact-checks found",
            }

        review = claims[0].get("claimReview", [{}])[0]
        rating = review.get("textualRating", "").lower()

        status_map = {
            "false": "debunked", "pants": "debunked", "incorrect": "debunked",
            "true": "verified", "accurate": "verified",
            "mixture": "mixture", "half": "mixture", "mostly": "mixture",
        }
        status = next((v for k, v in status_map.items() if k in rating), "unverified")

        return {
            "status": status,
            "claim": original,
            "textual_rating": review.get("textualRating"),
            "source_url": review.get("url"),
            "fact_checker": review.get("publisher", {}).get("name"),
            "review_date": review.get("reviewDate"),
        }

    # LangChain Tool
    @tool("google_fact_check")
    async def google_fact_check(self, claim: str) -> str:
        """
        Use this tool to verify factual claims against professional fact-checkers.
        Input: A single factual claim (e.g., "The Earth is flat")
        Output: Verification result with source
        """
        result = await self._search(claim)
        if result["status"] in ["verified", "debunked"]:
            return f"Fact-check result: {result['textual_rating']} by {result['fact_checker']}. Source: {result['source_url']}"
        return f"No reliable fact-check found for: {claim}"
    