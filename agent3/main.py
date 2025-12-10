"""
Agent 3 - Fact Checker Service
FastAPI application for verifying claims against fact-check databases
"""

import logging
from typing import List

from fastapi import FastAPI, HTTPException

from .config import settings
from .fact_checker import AsyncFactChecker
from .models import ClaimResult, VerifyRequest, VerifyResponse

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Veritas Agent 3 - Fact Checker",
    description="Fact-checking service using Google Fact Check Tools API",
    version="1.0.0",
)

# Initialize fact checker (singleton)
if not settings.google_fact_check_api_key:
    log.warning(" No API key configured! Set GOOGLE_FACT_CHECK_API_KEY in .env")

fact_checker = AsyncFactChecker(settings.google_fact_check_api_key)


# ==================
# API ENDPOINTS
# ==================


@app.get("/")
async def root():
    """Root endpoint - health check"""
    return {
        "service": "Agent 3 - Fact Checker",
        "status": "running",
        "version": "1.0.0",
    }


@app.get("/health")
async def health_check():
    """Detailed health check with system status"""
    cache_stats = fact_checker.get_cache_stats()

    return {
        "status": "healthy",
        "api_configured": bool(settings.google_fact_check_api_key),
        "cache": cache_stats,
    }


@app.post("/verify", response_model=VerifyResponse)
async def verify_endpoint(request: VerifyRequest):
    """
    Main verification endpoint - called by API Gateway.

    Only supports GRANULAR mode (text selection verification).
    Full URL mode is handled by the API Gateway orchestrator.

    Args:
        request: VerifyRequest with selection text

    Returns:
        VerifyResponse with verification results

    Raises:
        HTTPException: 400 if invalid request, 501 if full mode attempted
    """
    try:
        # GRANULAR MODE: User selected specific text
        if request.selection:
            mode = "granular"
            log.info(f" Granular mode: '{request.selection[:50]}...'")

            # Verify the selected text
            result = await fact_checker.verify(request.selection)

            return VerifyResponse(
                status="success",
                mode=mode,
                data={
                    "source": None,  # No source analysis in granular mode
                    "claims": [result],
                },
            )

        # FULL MODE: Not supported at agent level
        elif request.url:
            raise HTTPException(
                status_code=501,
                detail="Full URL verification must go through API Gateway. "
                "Agent 3 only handles granular claim verification.",
            )

        else:
            raise HTTPException(
                status_code=400,
                detail="Must provide 'selection' for claim verification",
            )

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        log.error(f"Error in verify endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/verify/batch")
async def verify_batch(claims: List[str]):
    """
    Batch verification endpoint - for internal use by Gateway.

    Verifies multiple claims in parallel for maximum speed.
    This is called by the API Gateway after Agent 2 extracts claims.

    Args:
        claims: List of claim strings to verify

    Returns:
        Dict with status and list of verification results

    Raises:
        HTTPException: 400 if invalid input
    """
    # Validation
    if not claims:
        raise HTTPException(status_code=400, detail="No claims provided")

    if len(claims) > settings.max_batch_size:
        raise HTTPException(
            status_code=400,
            detail=f"Too many claims (max {settings.max_batch_size} per request)",
        )

    try:
        results = await fact_checker.verify_multiple(claims)

        return {"status": "success", "count": len(results), "results": results}

    except Exception as e:
        log.error(f"Error in batch endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/cache")
async def clear_cache():
    """
    Clear the verification cache.

    Useful for testing or forcing fresh verification.
    In production with Redis, this would clear the Redis cache.
    """
    cache_stats = fact_checker.get_cache_stats()
    cache_size = cache_stats["cache_size"]

    fact_checker.cache.clear()

    return {"status": "success", "message": f"Cleared {cache_size} cached results"}


@app.get("/stats")
async def get_stats():
    """
    Get service statistics.

    Returns cache stats and other metrics.
    """
    return {
        "cache": fact_checker.get_cache_stats(),
        "config": {
            "api_timeout": settings.api_timeout,
            "max_batch_size": settings.max_batch_size,
            "cache_enabled": settings.cache_enabled,
        },
    }


# ==================
# SERVER STARTUP
# ==================

if __name__ == "__main__":
    import uvicorn

    log.info(f"Starting Agent 3 on {settings.host}:{settings.port}")

    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")
