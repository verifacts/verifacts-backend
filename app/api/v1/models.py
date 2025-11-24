from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any


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
    