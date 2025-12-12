# agents/fact_checker/agent.py
import logging
from typing import List, Dict, Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from app.services.llm_wrapper import llm_wrapper
from app.services.fact_checker.tools import GoogleFactCheckTool
from app.core.models import FactCheckVerdict
from app.core.config import config

log = logging.getLogger(__name__)


class FactCheckAgent:
    """
    Agent 3: Final fact-check judgment using Google Fact Check API + LLM reasoning
    """

    def __init__(self):
        self.llm = llm_wrapper.get_llm()
        self.tool = GoogleFactCheckTool(api_key=config.GOOGLE_FACT_CHECK_API_KEY)
        self.parser = JsonOutputParser(pydantic_object=FactCheckVerdict)

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """
        You are a professional fact-checker. Use the Google Fact Check tool result below to give a final verdict.

        Rules:
        - If a reputable fact-checker (Snopes, PolitiFact, AFP, etc.) rated it → trust them
        - "False", "Pants on Fire" → debunked
        - "True" → verified
        - "Mixture", "Mostly False" → mixture
        - No result → unverified
        - Be concise and neutral

        Return JSON only.
        {format_instructions}
            """),
            ("human", "Claim: {claim}\nTool result: {tool_result}")
        ])

        self.chain = self.prompt | self.llm | self.parser

    async def run(self, claim: str) -> Dict[str, Any]:
        log.info(f"FactCheckAgent verifying: {claim[:60]}...")

        # Step 1: Use tool to get raw fact-check data
        raw_result = await self.tool._search(claim)
        tool_output = str(raw_result)

        # Step 2: LLM makes final reasoned verdict
        try:
            verdict = await self.chain.ainvoke({
                "claim": claim,
                "tool_result": tool_output,
                "format_instructions": self.parser.get_format_instructions()
            })

            return {
                "agent": "fact_checker",
                "claim": claim,
                "verdict": verdict,
                "raw_tool_result": raw_result,
            }

        except Exception as e:
            log.error(f"LLM failed in FactCheckAgent: {e}")
            return {
                "agent": "fact_checker",
                "claim": claim,
                "verdict": {
                    "verdict": "unverified",
                    "confidence": 0.1,
                    "explanation": "Fact-check processing failed",
                    "sources": []
                },
                "error": str(e)
            }