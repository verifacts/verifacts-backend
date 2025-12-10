"""
Pydantic models for Agent 3 API requests and responses
"""

from typing import Optional

from pydantic import BaseModel


class VerifyRequest(BaseModel):
    """Request model for /verify endpoint"""

    url: Optional[str] = None
    selection: Optional[str] = None
    force_refresh: bool = False


class ClaimResult(BaseModel):
    """Result for a single claim verification"""

    claim: str
    status: str  # "verified", "debunked", "mixture", "unverified"
    textual_rating: Optional[str] = None
    corroboration_url: Optional[str] = None
    fact_checker: Optional[str] = None
    checked_date: Optional[str] = None


class VerifyResponse(BaseModel):
    """Response model for /verify endpoint"""

    status: str  # "success" or "error"
    mode: str  # "granular" or "full"
    data: dict
