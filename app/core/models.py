from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any, Literal


class AnalysisRequest(BaseModel):
    url: HttpUrl = Field(..., description="The URL of the webpage to analyze.")
    selection: Optional[str] = Field(
        None, 
        description="Optional specific text selection from the webpage."
        )
    force_refresh: bool = Field(
        False, 
        description="Whether to force refresh the cached analysis."
        )
    

class ClaimVerdict(BaseModel):
    claim: str
    verdict: str = Field(description="verified | debunked | mixture | unverified")
    confidence: Optional[float] = None
    explanation: Optional[str] = None
    sources: List[str] = Field(default_factory=list)

class SourceIdentity(BaseModel):
    trust_level: str = Field(description="high | medium | low | very_low")
    score: float = Field(ge=0, le=100)
    red_flags: List[str] = Field(default_factory=list)
    summary: Optional[str] = None

class VerdictSummary(BaseModel):
    overall_verdict: str
    summary: str
    total_claims: int
    verified_count: int
    debunked_count: int
    sources: List[str]

class AnalysisResponse(BaseModel):
    status: str = "success"
    source_identity: SourceIdentity
    claims: List[ClaimVerdict]
    verdict: VerdictSummary
    search_insights: Optional[List[Dict]] = None  # From Tavily
    
    
class Provenance(BaseModel):
    source: Literal["selection", "extracted", "user_provided"] = Field(..., description="Source of the claim.")
    url: Optional[HttpUrl] = Field(None, description="URL from which the claim was extracted, if applicable.")
    context: Optional[str] = Field(None, description="Contextual information about the claim.")
    
class Claim(BaseModel):
    claim_id: str
    text: str = Field(..., description="The atomic factual claim statement")
    normalized_text: Optional[str] = Field(None, description="Normalized version of the claim text.")
    provenance: Provenance = Field(..., description="Provenance information of the claim.")
    confidence: Optional[float] = Field(None, description="Confidence score of claim extraction (0.0 to 1.0).")
    claim_type: Literal["factual", "opinion", "mixed", "ambiguous"] = Field(..., description="Type of the claim.")
    
class CredibilityVerdict(BaseModel):
    trust_level: str = Field(..., description="Overall trust level of the source (e.g., high, medium, low).")
    score: float = Field(..., description="Credibility score of the source (0-100).")
    red_flags: List[str] = Field(..., description="List of identified red flags affecting credibility.")
    summary: str = Field(..., description="Summary of the credibility assessment.")
    source_used: list[str] = Field(..., description="List of sources used in the credibility assessment.")
    

class FactCheckVerdict(BaseModel):
    """Result for a single claim verification"""
    claim: str = Field(..., description="The factual claim being verified")
    verdict: str = Field(..., description="verified | debunked | mixture | unverified")
    textual_rating: Optional[str] = Field(None, description="Textual rating from the fact-checker")
    corroboration_url: Optional[str] = Field(None, description="URL to the fact-check source")
    fact_checker: Optional[str] = Field(None, description="Name of the fact-checking organization")
    checked_date: Optional[str] = None


class VerifyResponse(BaseModel):
    """Response model for /verify endpoint"""

    status: str  # "success" or "error"
    mode: str  # "granular" or "full"
    data: dict
    
# === Final Output Schema ===
class FinalReport(BaseModel):
    url: str = Field(..., description="Original URL")
    credibility: Dict = Field(..., description="Source credibility assessment")
    claims: List[str] = Field(..., description="Extracted factual claims")
    fact_checks: List[Dict] = Field(..., description="Fact-check verdicts per claim")
    search_insights: List[Dict] = Field(default=[], description="Tavily search results with snippets for enrichment")
    overall_verdict: str = Field(..., description="Final truth rating: verified | debunked | mixture | unverified")
    summary: str = Field(..., description="One-paragraph overall summary")
    sources: List[str] = Field(default=[], description="Key corroborating URLs")
    
    
