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
    Uses search_insights (LLM-enriched Tavily) as primary verdict source.
    Falls back to Google Fact Check if needed.
    """
    logger.info(f"Received analysis request for URL: {request.url}")
    if not request.url and not request.selection:
        raise HTTPException(status_code=400, detail="Either 'url' or 'selection' must be provided.")
    
    logger.info("Starting orchestrator...")

    try:
        result = await run_orchestrator(
            url=str(request.url) if request.url else " ",
            selection=request.selection or ""
        )
        logger.info("Orchestrator completed successfully.")

        credibility = result.credibility
        claims_raw = result.claims
        fact_checks = result.fact_checks
        search_insights = result.search_insights  # List of dicts with 'claim' and 'insights'

        # === Build claim verdicts — prioritize search_insights (LLM reasoning) ===
        claim_verdicts = []
        verified_count = 0
        debunked_count = 0

        # Create a map from claim text → search insight for fast lookup
        search_map = {
            insight["claim"]: insight["insights"]
            for insight in search_insights
            if insight["status"] == "success" and "insights" in insight
        }

        # Map fact-check results too (for fallback)
        fact_check_map = {}
        for fc in fact_checks:
            if "claim" in fc.get("verdict", {}):
                fact_check_map[fc["verdict"]["claim"]] = fc["verdict"]

        for claim_text in claims_raw:
            insight_data = search_map.get(claim_text, {})

            if insight_data:
                verdict = insight_data.get("verdict", "unverified")
                confidence = insight_data.get("confidence")
                explanation = insight_data.get("llm_summary") or insight_data.get("summary")
                # ← FIXED: Only URLs
                sources = [
                    src["url"] 
                    for src in insight_data.get("key_sources", []) 
                    if isinstance(src, dict) and src.get("url")
                ]
            else:
                fc_verdict = fact_check_map.get(claim_text, {})
                verdict = fc_verdict.get("verdict", "unverified")
                confidence = None
                explanation = fc_verdict.get("textual_rating") or "No fact-check available"
                sources = [fc_verdict.get("source_url")] if fc_verdict.get("source_url") else []


            # Count for stats
            if verdict == "verified":
                verified_count += 1
            elif verdict == "debunked":
                debunked_count += 1

            claim_verdicts.append(ClaimVerdict(
                claim=claim_text,
                verdict=verdict,
                confidence=confidence * 100 if confidence is not None else None,  # Convert 0-1 → 0-100 if needed
                explanation=explanation,
                sources=sources
            ))

        # === Overall verdict — use LLM's final verdict if available, else fallback ===
        overall_verdict = result.overall_verdict or "unverified"
        final_summary = result.summary or "Analysis completed."

        # Fallback logic if LLM failed
        if overall_verdict == "unverified" and len(claims_raw) > 0:
            if verified_count == len(claims_raw):
                overall_verdict = "verified"
            elif debunked_count == len(claims_raw):
                overall_verdict = "debunked"
            elif verified_count > debunked_count:
                overall_verdict = "mostly_verified"
            elif debunked_count > verified_count:
                overall_verdict = "mostly_debunked"
            else:
                overall_verdict = "mixture"

        return AnalysisResponse(
            source_identity=SourceIdentity(
                trust_level=credibility.get("trust_level", "unknown"),
                score=credibility.get("score", 50.0),
                red_flags=credibility.get("red_flags", []),
                summary=credibility.get("summary")
            ),
            claims=claim_verdicts,
            verdict=VerdictSummary(
                overall_verdict=overall_verdict,
                summary=final_summary,
                total_claims=len(claims_raw),
                verified_count=verified_count,
                debunked_count=debunked_count,
                sources=result.sources  # Already aggregated in compile_report_node
            ),
            search_insights=search_insights  # Full raw insights for debugging/transparency
        )

    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")