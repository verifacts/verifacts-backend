# app/api/v1/endpoints.py
import logging
from fastapi import APIRouter, HTTPException
from app.services.orchestrator import run_orchestrator
from app.core.models import AnalysisRequest, AnalysisResponse, SourceIdentity, VerdictSummary, ClaimVerdict
from app.core.config import config

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter(prefix=config.API_PREFIX, tags=["v1"])

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_content(request: AnalysisRequest) -> AnalysisResponse:
    """
    Main endpoint: Analyze a URL and optional text selection.
    Runs the full multi-agent LangGraph pipeline.
    """
    logger.info(f"Received analysis request for URL: {request.url}")

    try:
        # Run the full orchestrator
        result = await run_orchestrator(
            url=str(request.url),
            selection=request.selection or ""
        )

        # Extract data safely
        credibility = result.credibility
        claims_raw = result.claims
        fact_checks = result.fact_checks
        search_insights = result.search_insights

        # Build claim verdicts
        claim_verdicts = []
        verified_count = 0
        debunked_count = 0

        for i, claim_text in enumerate(claims_raw):
            check = fact_checks[i] if i < len(fact_checks) else {}
            verdict_data = check.get("verdict", {})
            
            verdict = verdict_data.get("verdict", "unverified")
            if verdict == "verified":
                verified_count += 1
            elif verdict == "debunked":
                debunked_count += 1

            claim_verdicts.append(ClaimVerdict(
                claim=claim_text,
                verdict=verdict,
                confidence=verdict_data.get("confidence"),
                explanation=verdict_data.get("explanation"),
                sources=verdict_data.get("sources", [])
            ))

        # Overall verdict logic
        total = len(claims_raw)
        if total == 0:
            overall = "no_claims"
        elif verified_count == total:
            overall = "verified"
        elif debunked_count == total:
            overall = "debunked"
        elif verified_count > debunked_count:
            overall = "mostly_verified"
        elif debunked_count > verified_count:
            overall = "mostly_debunked"
        else:
            overall = "mixture"

        return AnalysisResponse(
            source_identity=SourceIdentity(
                trust_level=credibility.get("trust_level", "unknown"),
                score=credibility.get("score", 50.0),
                red_flags=credibility.get("red_flags", []),
                summary=credibility.get("summary")
            ),
            claims=claim_verdicts,
            verdict=VerdictSummary(
                overall_verdict=overall,
                summary=result.summary,
                total_claims=total,
                verified_count=verified_count,
                debunked_count=debunked_count,
                sources=result.sources
            ),
            search_insights=search_insights
        )

    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )