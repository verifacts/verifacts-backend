"""
Core fact-checking logic for Agent 3
"""

import asyncio
import hashlib
import logging
from typing import Dict, List, Optional

import aiohttp

from .config import settings

log = logging.getLogger(__name__)


class AsyncFactChecker:
    """
    Async Fact Checker that verifies claims using Google Fact Check API.
    Supports caching and parallel verification of multiple claims.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = settings.fact_check_api_url

        # In-memory cache (TODO: Replace with Redis in production)
        self.cache = {}

    def _hash_claim(self, claim: str) -> str:
        """
        Create unique hash for caching.

        Args:
            claim: Statement to hash

        Returns:
            SHA256 hash of the claim
        """
        cleaned = claim.lower().strip()
        return hashlib.sha256(cleaned.encode()).hexdigest()

    def _check_cache(self, claim: str) -> Optional[dict]:
        """
        Check if claim result is cached.

        Args:
            claim: Statement to check

        Returns:
            Cached result or None
        """
        if not settings.cache_enabled:
            return None

        claim_hash = self._hash_claim(claim)

        if claim_hash in self.cache:
            log.info(f"✓ Cache HIT: {claim[:40]}...")
            return self.cache[claim_hash]

        log.info(f"✗ Cache MISS: {claim[:40]}...")
        return None

    def _save_to_cache(self, claim: str, result: dict):
        """
        Save result to cache.

        Args:
            claim: Statement
            result: Verification result
        """
        if not settings.cache_enabled:
            return

        claim_hash = self._hash_claim(claim)
        self.cache[claim_hash] = result
        log.info(f"Cached: {claim[:40]}...")

    async def _call_google_api(
        self, claim: str, session: aiohttp.ClientSession
    ) -> dict:
        """
        Call Google Fact Check API asynchronously.

        Args:
            claim: Statement to fact-check
            session: aiohttp ClientSession for making requests

        Returns:
            API response as dict
        """
        params = {"key": self.api_key, "query": claim, "languageCode": "en"}

        try:
            log.info(f" Querying API: {claim[:40]}...")

            async with session.get(
                self.base_url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=settings.api_timeout),
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    log.error(f"❌ API Error: Status {response.status}")
                    return {"claims": []}

        except asyncio.TimeoutError:
            log.warning(f" Timeout: {claim[:40]}...")
            return {"claims": []}
        except Exception as e:
            log.error(f"❌ Unexpected error: {e}")
            return {"claims": []}

    def _parse_api_response(self, api_response: dict, original_claim: str) -> dict:
        """
        Parse Google's API response into our standard format.

        Args:
            api_response: Raw API response
            original_claim: The original claim text

        Returns:
            Standardized claim result
        """
        claims = api_response.get("claims", [])

        if not claims:
            return {
                "claim": original_claim,
                "status": "unverified",
                "reason": "No fact-checks available",
                "textual_rating": None,
                "corroboration_url": None,
                "fact_checker": None,
                "checked_date": None,
            }

        # Extract first (most relevant) result
        first_result = claims[0]
        claim_review = first_result.get("claimReview", [{}])[0]
        textual_rating = claim_review.get("textualRating", "").lower()

        status = self._map_rating_to_status(textual_rating)

        return {
            "claim": original_claim,
            "status": status,
            "textual_rating": textual_rating,
            "corroboration_url": claim_review.get("url"),
            "fact_checker": claim_review.get("publisher", {}).get("name"),
            "checked_date": claim_review.get("reviewDate"),
        }

    def _map_rating_to_status(self, rating: str) -> str:
        """
        Map Google's textual ratings to our status codes.

        Args:
            rating: Google's rating (e.g., "False", "True", "Mixture")

        Returns:
            Our status: "verified", "debunked", "mixture", or "unverified"
        """
        if any(word in rating for word in ["false", "pants on fire", "incorrect"]):
            return "debunked"
        elif any(word in rating for word in ["true", "correct", "accurate"]):
            return "verified"
        elif any(word in rating for word in ["mixture", "half", "mostly"]):
            return "mixture"
        else:
            return "unverified"

    async def verify(self, claim: str) -> dict:
        """
        Verify a single claim (main public method).

        Args:
            claim: Statement to fact-check

        Returns:
            Verification result
        """
        # Check cache first
        cached_result = self._check_cache(claim)
        if cached_result:
            return cached_result

        # Call API
        async with aiohttp.ClientSession() as session:
            api_response = await self._call_google_api(claim, session)

        # Parse response
        result = self._parse_api_response(api_response, claim)

        # Save to cache
        self._save_to_cache(claim, result)

        return result

    async def verify_multiple(self, claims: List[str]) -> List[dict]:
        """
        Verify multiple claims in parallel (FAST).

        Args:
            claims: List of statements to verify

        Returns:
            List of verification results
        """
        log.info(f" Verifying {len(claims)} claims in parallel...")

        # Create tasks for all claims
        tasks = [self.verify(claim) for claim in claims]

        # Run all at once
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any errors
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                log.error(f"Error verifying claim {i}: {result}")
                processed_results.append(
                    {
                        "claim": claims[i],
                        "status": "unverified",
                        "reason": "Processing error",
                    }
                )
            else:
                processed_results.append(result)

        return processed_results

    def get_cache_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dict with cache info
        """
        return {
            "cache_enabled": settings.cache_enabled,
            "cache_size": len(self.cache),
            "cache_type": "in-memory",  # TODO: Change to "redis" when implemented
        }
