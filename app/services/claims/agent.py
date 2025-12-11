import logging
import uuid
from typing import List, Dict, Any, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from app.services.llm_wrapper import llm_wrapper
from app.services.claims.tools import ClaimTools
from app.core.models import Claim, Provenance

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ExtractedClaimItem(BaseModel):
    text: str = Field(..., description="The extracted claim text.")
    type: str = Field(..., description="The type of the claim (factual, opinion, etc.).")
    
    
class ClaimsList(BaseModel):
    claims: List[ExtractedClaimItem] = Field(..., description="List of extracted claims.")
    
    
    
class ClaimExtractionAgent:
    """
    Agent 2: Claim Extraction Agent.
    Roles:
    1. Decide strategy (Passthrough vs Atomization).
    2. Call Scraping Tools if needed.
    3. Use LLM to extract and classify claims.
    """
    
    def __init__(self):
        self.llm = llm_wrapper.get_llm()
        self.output_parser = JsonOutputParser(pydantic_object=ClaimsList)
        self.tools = ClaimTools()
        
    
    async def run(self, url: str, selection: Optional[str] = None) -> List[Claim]:
        """
        Main method to run the Claim Extraction Agent.
        """
        text_to_process = ""
        source_type = "selection"
        context_url = url
        cleaned_bg = ""  # Initialize here to avoid 'not defined' errors
        
        if selection:
            logger.info("Using user-provided text selection for claim extraction.")
            text_to_process = selection
            
            clean_sel, _ = self.tools.sanitize_text(selection, max_length=5000)
            if self.tools.looks_like_propmpt_injection(clean_sel):
                logger.warning("Potential prompt injection detected in user selection.")
                return [self._create_ambiguous_claim("Potential prompt injection detected in user selection.", url, source_type)]
            
            text_to_process = clean_sel
            
            if url:
                try:
                    logger.info(f"Fetching background context from FireCrawl for URL: {url}")
                    full_page_text = await self.tools.scrape_article_text.ainvoke(url)
                    if full_page_text:
                        context_snippet, _ = self.tools.sanitize_text(full_page_text, max_length=2000)
                        cleaned_bg = context_snippet.replace("\n", " ")
                        logger.info("Successfully fetched background context for selection.")
                
                except Exception as e:
                    logger.warning(f"Failed to fetch background context from FireCrawl: {str(e)}")
        
        elif url:
            logger.info(f"No text selection provided, scraping article text from {url}.")
            
            scraped_text = await self.tools.scrape_article_text.ainvoke(url)
            
            if not scraped_text:
                logger.warning("No text could be extracted from the article.")
                return [self._create_ambiguous_claim("No text could be extracted from the article.", url, "extracted")]
            
            text_to_process = scraped_text
            source_type = "extracted"
            
        if not text_to_process:
            logger.error("No text available for claim extraction after processing.")
            return [self._create_ambiguous_claim("No text available for claim extraction.", url, source_type)]
        
        
        is_short_selection = len(text_to_process.split()) < 50
        has_complexity = " and " in text_to_process.lower() or ";" in text_to_process or "," in text_to_process
        
        should_atomize = (source_type == "extracted") or (has_complexity and cleaned_bg != "")
        
        if should_atomize and self.llm:
            # Fixed: Correct argument order matching method signature
            return await self._atomize_and_extract_claims(
                text=text_to_process,
                url=url,
                source=source_type,  # This is the source type (selection/extracted)
                source_type=source_type,
                context=cleaned_bg
            )
        else:
            return [self._create_ambiguous_claim(text_to_process, url, source_type)]
        

    async def _atomize_and_extract_claims(
        self, 
        text: str, 
        url: Optional[str], 
        source: str, 
        source_type: str, 
        context: Optional[str] = None
    ) -> List[Claim]:
        """
        Atomizes the text into multiple claims using the LLM.
        """
        
        context_instruction = ""
        
        if source == "selection" and context:
            context_instruction = (
                f"CONTEXT INFO:\n"
                f"The user selected the text below from a webpage ({url or 'unknown'}).\n"
                f"Here is a snippet of the page content to help you understand the topic:\n"
                f"--- BEGIN CONTEXT ---\n{context}\n--- END CONTEXT ---\n"
                f"Use this context to resolve ambiguities (e.g. what 'it' refers to), but ONLY extract claims from the 'USER SELECTION'."
            )

        elif source == "selection" and url:
            context_instruction = f"SOURCE URL: {url}. Use the domain to infer the likely topic if needed."
            
        elif source == "extracted":
            context_instruction = f"SOURCE URL: {url or 'unknown'}. Use the domain to infer the likely topic if needed."
            
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert fact-checker. "
                       "Your task is to extract distinct, checkable factual claims from the provided text.\n"
                       "Rules:\n"
                       "1. Split compound statements (e.g. 'X is true and Y is false' -> [X, Y]).\n"
                       "2. Ignore pure opinions or rhetorical questions.\n"
                       "3. Keep claims concise and self-contained.\n"
                       "{context_instruction}\n\n"
                       "{format_instructions}"),
            ("user", "USER SELECTION to analyze:\n{text}")
        ])
        
        chain = prompt | self.llm | self.output_parser
        
        try: 
            result = await chain.ainvoke({
                "text": text,
                "context_instruction": context_instruction,
                "format_instructions": self.output_parser.get_format_instructions()
            })
            logger.info(f"Successfully extracted claims using atomization {result}.")
            
            claims = []
            
            # Handle both dict and list responses from the parser
            claims_list = result.get("claims", []) if isinstance(result, dict) else result
            
            for item in claims_list:
                if isinstance(item, dict):
                    claim_text = item.get("text", str(item))
                    claim_type = item.get("type", "factual")
                else:
                    claim_text = str(item)
                    claim_type = "factual"
                
                claims.append(Claim(
                    claim_id=str(uuid.uuid4()),
                    text=claim_text,
                    normalized_text=claim_text.lower().strip(),
                    claim_type=claim_type,
                    provenance=Provenance(
                        source=source_type,
                        url=url,
                        context=context_instruction[:200] + "..." if context_instruction else None,
                    ),
                    confidence=0.9 if claim_type == "factual" else 0.6
                ))
            logger.info(f"Extracted {len(claims)} claims using atomization.")
            return claims
        
        except Exception as e:
            logger.error(f"Error during claim atomization and extraction: {str(e)}")
            # Ensure source_type has a valid value for Provenance
            valid_source_type = source_type if source_type in ("selection", "extracted", "user_provided") else "extracted"
            return [self._create_ambiguous_claim("Error during claim extraction.", url, valid_source_type)]
        
    def _create_ambiguous_claim(self, text: str, url: Optional[str], source_type: str) -> Claim:
        """Fallback to create an ambiguous claim when extraction fails."""
        # Ensure source_type has a valid value
        valid_source_type = source_type if source_type in ("selection", "extracted", "user_provided") else "extracted"
        return Claim(
            claim_id=str(uuid.uuid4()),
            text=text,
            normalized_text=text.lower().strip(),
            claim_type="ambiguous",
            provenance=Provenance(
                source=valid_source_type,
                url=url,
                context=text[:100] + "..." if text else None
            ),
            confidence=0.0
        )

# Example Usage:
async def main():
    url = "https://www.nbcnews.com/politics/donald-trump/trump-cnn-warner-bros-discovery-netflix-paramount-rcna248518/"
    selection = None  # or some specific text selection
    agent = ClaimExtractionAgent()
    claims = await agent.run(url, selection)
    for claim in claims:
        print(f"Claim ID: {claim.claim_id}, Text: {claim.text}, Type: {claim.claim_type}, Confidence: {claim.confidence}")
        
if __name__ == "__main__":
    import asyncio
    asyncio.run(main())