import logging
from fastapi import APIRouter, HTTPException, Depends
from app.api.v1.models import AnalysisRequest, AnalysisResponse, IdentityData, VerdictData
from app.core.config import config

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter(prefix=config.API_PREFIX, tags=["v1"])

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_content(request: AnalysisRequest) -> AnalysisResponse:
    """
    Core v1 endpoint to analyze and verify the sources of web contents.
    Triggers the analysis pipeline and multi-agent Langgraph workflow.
    """
    try:
        initial_state = {
            "url": str(request.url),
            "selection": request.selection,
            "force_refresh": request.force_refresh,
            "claims": [],
            "errors": [],
            "verification_results": [],
            "extracted_claims": [],
        }
        logger.info(f"Starting analysis for URL: {request.url}")
        
        final_state = initial_state
        
        identity_data = IdentityData(
            verified=final_state.get("is_verified", False),
            score=final_state.get("credibility_score", 0.0),
        )
        verdict_data = VerdictData(
            status=final_state.get("verdict_status", "Unverified"),
            claims_counted=final_state.get("claims_counted", 0),
            claims_verified=final_state.get("claims_verified", 0),
            claims_sourced=final_state.get("claims_sourced", 0)
        )
        response = AnalysisResponse(
            status=final_state.get("status", "Completed"),
            verdict=verdict_data,
            details={
                {
                    "agent": report.get("agent_name", "unknown"),
                    "claims": report.get("output", {}),
                    "errors": report.get("errors", [])
                }
                for report in final_state.get("agent_reports", [])     
            },
            identity=identity_data
        )
        return response
    
    except Exception as e:
        logger.error(f"Error during analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis of web content failed {str(e)}")