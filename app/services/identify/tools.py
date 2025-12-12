import whois 
import tldextract
import aiohttp
import datetime
import re 
import asyncio
from urllib.parse import urlparse
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv

from langchain_core.tools import tool

load_dotenv()

from app.core.config import config

# class Config:
#     GOOGLE_APIS_KEY: Optional[str] = os.getenv("GOOGLE_APIS_KEY")
#     FIRECRAWL_API_KEY: Optional[str] = os.getenv("FIRECRAWL_API_KEY")
#     URLSCAN_API_KEY: Optional[str] = os.getenv("URLSCAN_API_KEY")
    
# config = Config()

import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class SourceCredibilityTool:
    """
    A collection of tools for verifying sources URLs.

    """
    @staticmethod
    def extract_domain(url: str) -> str:
        """
        Extract the domain from a given URL.
        """
        extracted = tldextract.extract(url)
        logger.info(f"Extracted components: {extracted}")
        if not extracted.suffix:
            logger.warning(f"No suffix found for URL: {url}")
            return "unknown"
        domain = f"{extracted.domain}.{extracted.suffix}"
        logger.info(f"Extracted domain: {domain}")  
        return domain
    
    @staticmethod
    async def _submit_to_urlscan(url: str) -> Optional[str]:
        """
        Submit a URL to urlscan.io for analysis and return the scan ID.
        """
        api_key = config.URLSCAN_API_KEY
        if not api_key:
            logger.error("URLSCAN_API_KEY is not set in the environment variables.")
            return None
        
        submit_url = "https://urlscan.io/api/v1/scan/"
        headers = {
            'Content-Type': 'application/json',
            'API-Key': api_key,
        }
        # logger.info(f"Headers for urlscan.io submission: {headers}")
        data = {
            'url': url,
            'visibility': 'public'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(submit_url, json=data, headers=headers) as response:
                    if response.status == 200:
                        resp_json = await response.json()
                        scan_id = resp_json.get('uuid')
                        result_url = f"https://urlscan.io/api/v1/result/{scan_id}/"
                        # logger.info(f"Submitted URL to urlscan.io: {data.get("result") or result_url}")
                        return data.get("result") or result_url
                    else:
                        text = await response.text()
                        logger.error(f"Failed to submit URL to urlscan.io, status code: {response.status} {text}")
                        return None
        except aiohttp.ClientError as e:
            logger.error(f"Error submitting URL to urlscan.io: {e}")
            return None
        
    @staticmethod
    async def _fetch_urlscan_result(result_url: str) -> Optional[Dict[str, Any]]:
        """
        Fetch the result of a urlscan.io analysis.
        """
        api_key = config.URLSCAN_API_KEY
        if not api_key:
            logger.error("URLSCAN_API_KEY is not set in the environment variables.")
            return None
        
        headers = {
            'API-Key': api_key,
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(result_url, headers=headers) as response:
                    if response.status == 200:
                        resp_json = await response.json()
                        # logger.info(f"Fetched urlscan.io result from: {result_url}")
                        return resp_json
                    else:
                        text = await response.text()
                        logger.error(f"Failed to fetch urlscan.io result, status code: {response.status} {text}")
                        return None
        except aiohttp.ClientError as e:
            logger.error(f"Error fetching urlscan.io result: {e}")
            return None
    
    def extract_credibility_signals(urlscan_result: Dict[str, Any]) -> Dict[str, Any]:
        data = urlscan_result
        page = data.get("page", {})
        stats = data.get("stats", {})
        verdicts = data.get("verdicts", {})
        task = data.get("task", {})
        lists = data.get("lists", {})

        return {
            "url": task.get("url"),
            "scan_date": task.get("time"),
            "screenshot_url": task.get("screenshotURL"),

            # Critical verdicts
            "malicious_detected": verdicts.get("overall", {}).get("malicious", False),
            "engine_detections": verdicts.get("engines", {}).get("maliciousTotal", 0),
            "suspicious_categories": verdicts.get("overall", {}).get("categories", []),

            # Domain & TLS age
            "domain_age_days": page.get("apexDomainAgeDays", 0),
            "tls_age_days": page.get("tlsAgeDays", 0),
            "is_new_domain": page.get("apexDomainAgeDays", 9999) < 180,
            "is_brand_new_tls": page.get("tlsAgeDays", 9999) < 60,

            # Security posture
            "secure_percentage": stats.get("securePercentage", 100),
            "uses_mixed_content": stats.get("securePercentage", 100) < 98,

            # Hosting
            "server": page.get("server"),
            "asn": page.get("asn"),
            "asn_name": page.get("asnname"),
            "ip": page.get("ip"),

            # Privacy / trackers (approximate)
            "total_requests": sum(s.get("count", 0) for s in stats.get("resourceStats", [])),
            "third_party_domains": len(lists.get("domains", [])) - 1,

            # Suspicious patterns
            "has_data_urls": any("data:" in r.get("request", {}).get("url", "") for r in data.get("data", {}).get("requests", [])),
            "redirects_to_suspicious": any(
                tldextract.extract(url).domain in ["bit", "tinyurl"] or tldextract.extract(url).suffix in ["ru", "xyz", "top"]
                for url in lists.get("linkDomains", [])
            ),

            # Bonus: popularity
            "umbrella_rank": next(
                (item["rank"] for item in data.get("meta", {}).get("processors", {}).get("umbrella", {}).get("data", []) if item["hostname"] == page.get("domain")),
                None
            ),
        }
    

    @staticmethod
    @tool("check_source_credibility")
    async def check_source_credibility(url: str) -> Dict[str, Any]:
        """
        Check the credibility of a source URL using urlscan.io.
        Returns a dictionary with credibility information.
        """
        result = {
            "url": url,
            "domain": SourceCredibilityTool.extract_domain(url),
            "urlscan_result": None,
            "verdict": None,
            "is_malicious": None,
            "suspicious": None,
            "categories": []
        }
        
        result_url = await SourceCredibilityTool._submit_to_urlscan(url)
        if not result_url:
            logger.error(f"Could not submit URL to urlscan.io: {url}")
            return result
        
        urlscan_data = None
        if result_url:
            for _ in range(10):  # Retry up to 10 times
                await asyncio.sleep(5)  # Wait before retrying
                urlscan_data = await SourceCredibilityTool._fetch_urlscan_result(result_url)
                if urlscan_data:
                    break

        urlscan_insights = {}
        
        if urlscan_data:
            result["urlscan_result"] = urlscan_data
            credibitility_signals = SourceCredibilityTool.extract_credibility_signals(urlscan_data)
            urlscan_insights.update(credibitility_signals)
            
            
        return urlscan_insights


    
# # # Example usage:
# async def main():
#     url = "https://bit.ly/3X9kP2m/"
#     identifier = SourceCredibilityTool()
    
#     domain = identifier.extract_domain(url)
#     print(f"Extracted domain: {domain}")
    
#     credibility = await identifier.check_source_credibility.ainvoke(url)
#     print(f"Source credibility report: {credibility}")
    
# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(main())