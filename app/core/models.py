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
    

class IdentityData(BaseModel):
    verified: bool = Field(..., description="Whether the source is verified.")
    score: float = Field(..., description="Credibility score of the source (0.0 to 1.0).")
    
class VerdictData(BaseModel):
    status: str = Field(..., description="Verdict status (e.g., true, false, mixed).")
    claims_counted: int = Field(0, description="Number of claims evaluated.")
    claims_verified: int = Field(0, description="Number of claims verified as true.")
    claims_sourced: int = Field(0, description="Number of claims with sources provided.")
    
class AnalysisResponse(BaseModel):
    status: str = Field(..., description="Status of the analysis request.")
    verdict: VerdictData = Field(..., description="Detailed verdict data.")
    identity: IdentityData = Field(..., description="Identity verification data of the source.")
    details: Dict[str, Any] = Field(..., description="Detailed agent reports and findings.")
    
    
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
    