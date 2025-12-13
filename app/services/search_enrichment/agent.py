# app/agents/search_enrichment/agent.py
import logging
from typing import Dict, Any, List
from datetime import datetime

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from app.services.llm_wrapper import llm_wrapper
from app.services.search_enrichment.tools import TavilySearchTool

log = logging.getLogger(__name__)

# Structured output from LLM
class SearchEnrichmentVerdict(BaseModel):
    claim: str = Field(..., description="Original claim")
    summary: str = Field(..., description="Clear, neutral 2-3 sentence summary of current reporting")
    confidence: float = Field(..., ge=0, le=1, description="Confidence in the summary (0-1)")
    verdict: str = Field(..., description="verified | debunked | mixture | unverified")
    key_sources: List[Dict[str, str]] = Field(..., description="Top 3 most relevant sources with title/url")
    notes: str = Field("", description="Any caveats, contradictions, or context")

class TavilySearchAgent:
    """
    Intelligent Search Enrichment Agent
    Uses Tavily tool + LLM to produce structured, reasoned insights.
    """

    def __init__(self):
        self.tool = TavilySearchTool()
        self.llm = llm_wrapper.get_llm()  # Low temp for factual
        self.parser = JsonOutputParser(pydantic_object=SearchEnrichmentVerdict)

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """
You are a professional research analyst enriching factual claims with current web reporting.

Your job:
- Summarize what reliable sources are saying about the claim
- Assess sentiment (confirmed, disputed, unverified, emerging)
- Highlight contradictions or gaps
- Select the 3 most credible sources
- Be concise, neutral, and evidence-based
- Make sure the responses are as STRAIGHTFORWARD AS THEY CAN BE

Use only the provided search results. Do not hallucinate.

{format_instructions}
"""),
            ("human", """
Claim: {claim}

Search Results:
{search_results}

Respond with valid JSON only.
""")
        ])

        self.chain = self.prompt | self.llm | self.parser

    async def run(self, claim: str) -> Dict[str, Any]:
        log.info(f"TavilySearchAgent analyzing: {claim[:60]}...")

        # Step 1: Raw search via tool
        query = f"fact check OR official OR reported: \"{claim}\" 2025"
        raw_result = await self.tool._search(query)

        if raw_result["status"] != "success":
            return {
                "claim": claim,
                "status": "failed",
                "error": raw_result.get("reason", "Search failed"),
                "insights": None
            }

        # Format search results for LLM
        sources_text = "\n".join(
            f"- {s['title']} ({s['domain']}): {s['snippet'][:500]}...\n  URL: {s['url']}"
            for s in raw_result["top_sources"]
        ) or "No sources found."

        search_context = f"""
Summary from search: {raw_result['summary']}
Total sources: {raw_result['total_results']}

Top Sources:
{sources_text}
""".strip()

        try:
            # Step 2: LLM reasoning
            llm_output = await self.chain.ainvoke({
                "claim": claim,
                "search_results": search_context,
                "format_instructions": self.parser.get_format_instructions()
            })

            return {
                "claim": claim,
                "status": "success",
                "insights": {
                    "llm_summary": llm_output.get("summary"),
                    "confidence": llm_output.get("confidence", 0.5),
                    "verdict": llm_output.get("verdict"),
                    "key_sources": llm_output.get("key_sources", []),
                    "notes": llm_output.get("notes", "")
                }
            }

        except Exception as e:
            log.error(f"LLM failed in TavilySearchAgent: {e}")
            # Fallback: return raw structured result
            return {
                "claim": claim,
                "status": "partial",
                "insights": {
                    "llm_summary": raw_result["summary"],
                    "confidence": 0.4,
                    "sentiment": raw_result["overall_sentiment"],
                    "key_sources": raw_result["top_sources"][:3],
                    "notes": "LLM reasoning failed — using raw search summary."
                }
            }


# Usage Example:
agent = TavilySearchAgent()

async def enrich_claim(claim: str) -> Dict[str, Any]:
    return await agent.run(claim)

if __name__ == "__main__":
    import asyncio

    test_claim = "The Earth is surely Flat."
    result = asyncio.run(enrich_claim(test_claim))
    print(result)