import logging
import asyncio
from typing import Dict, TypedDict, Annotated, List

from langchain_core.runnables import Runnable
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver  # For state persistence
from redis import Redis  # pip install redis
from langchain_community.cache import RedisCache

from app.services.identify.agent import SourceCredibilityAgent
from app.services.claims.agent import ClaimExtractionAgent
from app.services.fact_checker.agent import FactCheckAgent
from app.core.config import config
from app.services.shared_tools import tavily_search
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
    claims: Annotated[List[Dict], "Extracted claims"]
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

# === NEW: Tavily Enrichment (Always runs after extraction) ===
async def search_enrichment_node(state: WorkflowState) -> WorkflowState:
    if state.get("error") or not state.get("claims"): return state

    insights = []
    for claim in state["claims"]:
        try:
            query = f"fact check: {claim} site:reputable"
            results = await tavily_search.ainvoke({"query": query})
            insights.append({
                "claim": claim,
                "results": results,  # Includes snippets, answers, sources
                "sources": [r["url"] for r in results]
            })
        except Exception as e:
            logger.warning(f"Tavily failed for claim '{claim}': {e}")

    state["search_insights"] = insights
    return state

# === NEW: Compile Final Report ===
async def compile_report_node(state: WorkflowState) -> WorkflowState:
    # LLM summarizes overall
    prompt = ChatPromptTemplate.from_template("""
    Based on this state, generate final verdict and summary:
    State: {state_json}

    Overall verdict: Most claims verified → verified; most debunked → debunked; mixed → mixture
    """)
    output_parser = JsonOutputParser(pydantic_object=FinalReport)
    llm = llm_wrapper.get_llm()
    chain = prompt | llm | output_parser
    try:
        compiled = await chain.ainvoke({"state_json": str(state)})
        state["overall_verdict"] = compiled.get("overall_verdict", "unverified")
        state["summary"] = compiled.get("summary", "No summary generated")
        state["sources"] = [s for insight in state.get("search_insights", []) for s in insight["sources"]]
    except Exception as e:
        state["error"] = f"Report compilation failed: {e}"
    return state

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
    "credibility_node", decide_next_step
)
workflow.add_edge("extraction_node", "search_enrichment_node")
workflow.add_edge("search_enrichment_node", "factcheck_node")
workflow.add_edge("factcheck_node", "compile_report_node")
workflow.add_edge("compile_report_node", END)


memory = MemorySaver()
graph = workflow.compile(checkpointer=memory)


async def run_orchestrator(url: str, selection:str) -> WorkflowState:
    initial_state: WorkflowState = {
        "url": url,
        "selection": selection,
        "credibility": {},
        "claims": [],
        "fact_checks": [],
        "error": "",
    }
    final_state = await graph.ainvoke(initial_state, config={"configurable": {"thread_id": "main"}})
    return final_state

# Example usage
if __name__ == "__main__":
    test_url = "https://www.nbcnews.com/politics/donald-trump/trump-cnn-warner-bros-discovery-netflix-paramount-rcna248518"
    test_selection = "Paramount initiated a hostile bid, offering shareholders $30 per share."
    
    result_state = asyncio.run(run_orchestrator(test_url, test_selection))
    if result_state.get("error"):
        logger.error(f"Orchestration failed: {result_state['error']}")
    else:
        logger.info(f"Orchestration completed successfully. Fact-checks: {result_state['fact_checks']}")
