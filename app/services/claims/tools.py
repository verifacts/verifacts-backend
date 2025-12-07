import logging
import re
from typing import List, Dict, Any, Tuple, Optional
from langchain_core.tools import tool
from langchain_community.document_loaders.firecrawl import FireCrawlLoader

from app.core.config import config

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ClaimTools:
    """
    A collection of tools for fetching, extracting and cleaning texts 
    for the claim extraction agent.
    """
    
    @staticmethod
    def sanitize_text(text: str, max_length: Optional[int] = None) -> Tuple[str, ...]:
        """
        Cleans and sanitizes the input text by removing unwanted characters,
        excessive whitespace, and truncating to max_length if specified.
        
        Args:
            text (str): The input text to sanitize.
            max_length (Optional[int]): Maximum length of the sanitized text.
            
        Returns:
            (cleaned_text, was_truncated): A tuple containing the cleaned text and a boolean indicating if truncation occurred.
        
        """
        if not text:
            return "", False
        
        text = text.replace("\u200b", " ").replace("\ufeff", "")  # Remove zero-width spaces and BOM
        cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
        cleaned = " ".join(cleaned.split())  # Collapse multiple spaces/newlines
        
        was_truncated = False
        if max_length and len(cleaned) > max_length:
            cleaned = cleaned[:max_length]
            was_truncated = True
        
        return cleaned, was_truncated
    
    @staticmethod
    @tool("scrape_article_text")
    def scrape_article_text(url: str) -> str:
        """
        Extracts the main body text from an article given its URL.
        Useful when user provides a URL without specific text selection.
        """
        try:
            from newspaper import Article
            
            logger.info(f"Scraping article text from URL: {url}")
            article = Article(url)
            article.download()
            article.parse()
            
            text = article.text
            if not text or len(text.strip()) == 50:
                logger.warning(f"No text extracted from article at URL: {url}")
                return ""
        
        except Exception as e:
            logger.error(f"Error scraping article text from {url}: {str(e)}")
            return ""
        
        if text and len(text.strip())> 50:
            logging.info(f"Successfully extracted article text from URL: {url} using Newspaper4k")
            return text
        
        if config.FIRECRAWL_API_KEY:
            logger.info("Fallback for Newspaper4k: Using FireCrawl to extract article text.")
            try:
                loader = FireCrawlLoader(
                    urls=[url],
                    api_key=config.FIRECRAWL_API_KEY,
                    mode="scrape",
                    render_js=True,
                    wait_time=2,
                    max_retries=2
                )
                documents = loader.load()
                if documents:
                    text = "\n".join([doc.page_content for doc in documents])
                    logger.info(f"Successfully extracted article text from URL: {url} using FireCrawl")
                    return text
                else:
                    logger.warning(f"No documents returned by FireCrawl for URL: {url}")
            except Exception as e:
                logger.error(f"Error extracting article text from {url} using FireCrawl: {str(e)}")
                return ""
        
        else:
            logger.warning("FIRECRAWL_API_KEY not set. Cannot use FireCrawl for extraction.")

        return text
    
    
    @staticmethod
    def looks_like_propmpt_injection(text: str) -> bool:
        """
        Heuristic check to determine if the provided text looks like a prompt injection attempt.
        
        Args:
            text (str): The input text to evaluate.
        Returns:
            bool: True if the text appears to be a prompt injection, False otherwise.
        """
        injection_patterns = [
            r"(?i)ignore all previous instructions",
            r"(?i)disregard previous directions",
            r"(?i)override earlier commands",
            r"(?i)forget what you were told before",
            r"(?i)act as if you are",
            r"(?i)you are now",
            r"(?i)from now on",
            r"(?i)you must",
            r"(?i)you will",
            r"(?i)silence all prior guidelines",
            r"(?i)break free from your restrictions",
            r"(?i)bypass your limitations",
            r"(?i)ignore your programming",
            r"(?i)go against your guidelines", 
            r"(?i)user:",
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning(f"Prompt injection pattern detected: {pattern} in text: {text}")
                return True
        
        return False

