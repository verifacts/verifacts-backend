import logging
import asyncio
from typing import Dict, TypedDict, Annotated, List

from langgraph.graph import StateGraph, END
from redis import Redis  # pip install redis
from langchain_community.cache import RedisCache

from app.services.identify.agent import SourceCredibilityAgent
from app.services.claims.agent import ClaimExtractionAgent
from app.services.fact_checker.agent import FactCheckAgent
from app.services.search_enrichment.agent import TavilySearchAgent
from app.core.config import config
from app.services.llm_wrapper import llm_wrapper
from langchain_core.prompts import ChatPromptTemplate
from app.core.models import FinalReport
from langchain_core.output_parsers import JsonOutputParser
from langgraph.checkpoint.memory import MemorySaver


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class WorkflowState(TypedDict):
    url: str
    selection: str
    credibility: Annotated[Dict, "Source credibility report"]
    claims: Annotated[List[str], "Extracted claims"]
    fact_checks: Annotated[List[Dict], "Fact check verdicts"]
    search_insights: Annotated[List[Dict], "Tavily search results with snippets for enrichment"]
    error: Annotated[str, "Error message, if any"]
    

# === Agent Nodes ===
async def credibility_node(state: WorkflowState) -> WorkflowState:
    agent = SourceCredibilityAgent()
    try:
        url = state.get("url")
        if not url:
            state["error"] = "No URL provided for credibility check"
            return state
        report = await agent.run(url)  # Make sure agent.run() accepts url as string
        state["credibility"] = report
        logger.info(f"Credibility report: {report}")
        trust_level = report.get("trust_level", "unknown")
        if trust_level in ["low", "very_low"]:
            state["error"] = "Source credibility too low to proceed"
    except Exception as e:
        logger.error(f"Credibility check error: {str(e)}")
        state["error"] = f"Credibility check failed: {str(e)}"
    return state

async def extraction_node(state: WorkflowState) -> WorkflowState:
    if state.get("error"):
        return state  # Skip if previous error
    agent = ClaimExtractionAgent()
    try:
        # Build verdict dict from state to pass to agent
        verdict = {
            "url": state.get("url"),
            "selection": state.get("selection"),
            "trust_level": state.get("credibility", {}).get("trust_level"),
            "score": state.get("credibility", {}).get("score"),
        }
        claims = await agent.run(verdict)  # Pass verdict to agent
        logger.info(f"Extracted {len(claims)} claims")
        state["claims"] = [c.text for c in claims if c.claim_type == "factual"]
    except Exception as e:
        logger.error(f"Claim extraction error: {str(e)}")
        state["error"] = f"Claim extraction failed: {str(e)}"
    return state

async def factcheck_node(state: WorkflowState) -> WorkflowState:
    if state.get("error") or not state.get("claims"):
        return state  # Skip if previous error or no claims
    agent = FactCheckAgent()
    try:
        fact_checks = []
        for claim in state["claims"]:
            result = await agent.run(claim)
            logger.info(f"Fact-check result for claim '{claim[:30]}...': {result}")
            fact_checks.append(result)
        state["fact_checks"] = fact_checks
    except Exception as e:
        state["error"] = f"Fact-checking failed: {str(e)}"
    return state

# === NEW: Search Enrichment with LLM Reasoning ===
async def search_enrichment_node(state: WorkflowState) -> WorkflowState:
    if state.get("error") or not state.get("claims"):
        state["search_insights"] = []
        return state

    if not config.TAVILY_API_KEY:
        logger.warning("Tavily not configured — skipping search enrichment")
        state["search_insights"] = []
        return state

    agent = TavilySearchAgent()
    insights = []

    for claim in state["claims"]:
        try:
            result = await agent.run(claim)
            insights.append(result)
            logger.info(f"Successfully ran Tavily Search enrichment for claim '{claim[:30]}...': {result}")
        except Exception as e:
            logger.error(f"Search enrichment failed for '{claim}': {e}")
            insights.append({
                "claim": claim,
                "status": "failed",
                "error": str(e),
                "insights": None
            })

    state["search_insights"] = insights
    return state

# === NEW: Compile Final Report ===
async def compile_report_node(state: WorkflowState) -> WorkflowState:
    # LLM summarizes overall
    prompt = ChatPromptTemplate.from_template("""
You are a fact-check report compiler. Analyze the following state and generate a final report.

State:
- URL: {url}
- Source Credibility: {credibility}
- Claims Extracted: {claims}
- Fact Check Results: {fact_checks}
- Search Insights: {search_insights}

Rules for verdict:
- If most claims are verified → "verified"
- If most claims are debunked → "debunked"  
- If mixed results → "mixture"
- If insufficient evidence → "unverified"

{format_instructions}

Respond ONLY with valid JSON. Do not include any markdown formatting, explanations, or text outside the JSON object.
""")
    llm = llm_wrapper.get_llm()
    output_parser = JsonOutputParser(pydantic_object=FinalReport)
    chain = prompt | llm | output_parser
    
    try:
        compiled = await chain.ainvoke({
            "url": state.get("url", ""),
            "credibility": state.get("credibility", {}),
            "claims": state.get("claims", []),
            "fact_checks": state.get("fact_checks", []),
            "search_insights": state.get("search_insights", []),
            "format_instructions": output_parser.get_format_instructions()
        })
        logger.info(f"Compiled report: {compiled}")
        state["overall_verdict"] = compiled.get("overall_verdict", "unverified")
        state["summary"] = compiled.get("summary", "No summary generated")
        
    except Exception as e:
        logger.error(f"LLM report compilation failed: {str(e)}")
        # Fallback summary
        total_claims = len(state.get("claims", []))
        verified = sum(1 for fc in state.get("fact_checks", []) if fc.get("verdict", {}).get("verdict") == "verified")
        debunked = sum(1 for fc in state.get("fact_checks", []) if fc.get("verdict", {}).get("verdict") == "debunked")

        if total_claims == 0:
            verdict = "no_claims"
        elif verified == total_claims:
            verdict = "verified"
        elif debunked == total_claims:
            verdict = "debunked"
        elif verified > debunked:
            verdict = "mostly_verified"
        elif debunked > verified:
            verdict = "mostly_debunked"
        else:
            verdict = "mixture"

        state["overall_verdict"] = verdict
        state["summary"] = (
            f"Processed {total_claims} claims. "
            f"{verified} verified, {debunked} debunked. "
            "Web search provided additional context."
        )
    
    # === Extract ALL sources from both fact-checks AND Tavily insights ===
    sources_set = set()  # Deduplicate URLs

    # 1. From Google Fact Check (fact_checks)
    for fc in state.get("fact_checks", []):
        verdict_data = fc.get("verdict", {})
        source_url = verdict_data.get("source_url") or verdict_data.get("corroboration_url")
        if source_url:
            sources_set.add(source_url.strip())

    # 2. From TavilySearchAgent (search_insights)
    for insight in state.get("search_insights", []):
        if insight.get("status") != "success":
            continue
        insights_data = insight.get("insights", {})
        if not insights_data:
            continue

        # Prefer LLM-selected key_sources
        key_sources = insights_data.get("key_sources", [])
        for src in key_sources:
            url = src.get("url")
            if url:
                sources_set.add(url.strip())

        # Fallback: use raw top_sources if key_sources empty
        if not key_sources:
            raw = insights_data.get("raw_search", {})
            for src in raw.get("top_sources", []):
                url = src.get("url")
                if url:
                    sources_set.add(url.strip())

    state["sources"] = list(sources_set)  # Convert back to list

    logger.info(f"Compiled {len(state['sources'])} unique sources")
        
    
def decide_next_step(state: WorkflowState) -> str:
    cred = state.get("credibility", {}).get("verdict", {}).get("trust_level", "unknown")
    if cred in ["low", "very_low"]:
        return END  # Still skip if very low
    return "extraction_node"

# === Orchestrator ===
workflow = StateGraph(state_schema=WorkflowState)

workflow.add_node("credibility_node", credibility_node)
workflow.add_node("extraction_node", extraction_node)
workflow.add_node("search_enrichment_node", search_enrichment_node)
workflow.add_node("factcheck_node", factcheck_node)
workflow.add_node("compile_report_node", compile_report_node)

workflow.set_entry_point("credibility_node")

workflow.add_conditional_edges(
    "credibility_node",
    decide_next_step,
    {
        "extraction_node": "extraction_node",
        END: END
    }  # Fixed: Added mapping dict
)
workflow.add_edge("extraction_node", "search_enrichment_node")
workflow.add_edge("search_enrichment_node", "factcheck_node")
workflow.add_edge("factcheck_node", "compile_report_node")
workflow.add_edge("compile_report_node", END)


memory = MemorySaver()
graph = workflow.compile(checkpointer=memory)


async def run_orchestrator(url: str, selection: str) -> FinalReport:
    initial_state: WorkflowState = {
        "url": url,
        "selection": selection,
        "credibility": {},
        "claims": [],
        "fact_checks": [],
        "search_insights": [],
        "error": None,
    }
    final_state = await graph.ainvoke(initial_state, config={"configurable": {"thread_id": "main"}})
    
    # Return as FinalReport (with defaults for missing fields)
    return FinalReport(
        url=final_state.get("url", ""),
        credibility=final_state.get("credibility", {}),
        claims=final_state.get("claims", []),
        fact_checks=final_state.get("fact_checks", []),
        search_insights=final_state.get("search_insights", []),
        overall_verdict=final_state.get("overall_verdict", "unverified"),
        summary=str(final_state.get("summary", "No summary available")),
        sources=final_state.get("sources", [])
    )

# Example usage
if __name__ == "__main__":
    test_url = "https://www.nbcnews.com/politics/donald-trump/trump-cnn-warner-bros-discovery-netflix-paramount-rcna248518"
    test_selection = "Paramount initiated a hostile bid, offering shareholders $30 per share."
    
    result_state = asyncio.run(run_orchestrator(test_url, test_selection))
    logger.info(f"Final Verdict: {result_state.overall_verdict}")