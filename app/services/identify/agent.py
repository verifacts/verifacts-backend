import json
import logging
import uuid
from typing import Dict, Any, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from app.services.identify.tools import SourceCredibilityTool
from app.services.llm_wrapper import llm_wrapper

from app.core.config import config
from app.core.models import CredibilityVerdict

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class SourceCredibilityAgent:
    """
    Agent responsible for assessing the credibility of a source URL.
    Uses raw tools to gather data and an LLM to analyze and produce a verdict.
    """
    
    def __init__(self):
        self.llm = llm_wrapper.get_llm()
        self.tool = SourceCredibilityTool()
        self.output_parser = JsonOutputParser(
            pydantic_object=CredibilityVerdict
        )
        self.prompt = ChatPromptTemplate.from_messages([
                    ("system", """
        You are a senior fact-checking analyst specializing in source credibility evaluation.

        Using the technical signals below, produce a final credibility verdict.

        Guidelines:
        - Be strict: new domains (<6 months), no SSL history, or malicious verdicts → very_low
        - Established domains (>3 years), clean records → high
        - Heavy trackers/ads + obscure ASN → downgrade
        - Never trust sites flagged by Google Safe Browsing or urlscan.io as malicious
        - Bias: infer only if strong patterns (e.g., known partisan ASN or domain name)
        - BE CONCISE in your final verdict summary.
        - BE CONSISTENT between trust_level and score.

        Return valid JSON only.
        {format_instructions}
                    """.strip()),
                    ("human", "Assess credibility of this source:\n\n{report_json}")
                ])

        self.chain = self.prompt | self.llm | self.output_parser
        
    async def run(self, url: str) -> CredibilityVerdict:
        """
        Main method to run the Source Credibility Agent.
        
        Args:
            url (str): The URL of the source to assess.
            
        Returns:
            CredibilityVerdict: The credibility verdict of the source.
        """
        logger.info(f"Assessing credibility for URL: {url}")
        
        output_report = await self.tool.check_source_credibility.ainvoke(url)
        
        try:
            # logger.info(f"Generating credibility verdict using LLM using prompt: {self.prompt}.")
            verdict = await self.chain.ainvoke({
                "report_json": json.dumps(output_report, indent=2),
                "format_instructions": self.output_parser.get_format_instructions()               
            })
            # logger.info(f"Generated verdict: {verdict}")

            final_verdict = {
                "url": url,
                "trust_level": verdict.get("trust_level"),
                "score": verdict.get("score"),
                "red_flags": verdict.get("red_flags"),
                "summary": verdict.get("summary"),
                "source_used": verdict.get("source_used") if verdict.get("source_used") else [url]
            }
            # logger.info(f"Credibility verdict for {url}: {final_verdict}")
            
            return final_verdict
        
        except Exception as e:
            logger.error(f"Error generating credibility verdict for {url}: {str(e)}")
            return {
                "url": url,
                "trust_level": "unknown",
                "score": 0.0,
                "red_flags": ["error_generating_verdict"],
                "summary": "Could not generate credibility verdict due to an error.",
                "source_used": [url]
            }
            
# Example usage:
async def main():
    url = "https://databackedafrica.com/"
    agent = SourceCredibilityAgent()
    verdict = await agent.run(url)
    print(f"Credibility Verdict: {verdict}")
    
if __name__ == "__main__":
    import asyncio
    asyncio.run(main())