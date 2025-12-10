import whois 
import tldextract
import aiohttp
import datetime
import re 
from typing import Optional, Dict, Any
from langchain_community.document_loaders.firecrawl import FireCrawlLoader
import os
from dotenv import load_dotenv

load_dotenv()

# from app.core.config import config

class Config:
    GOOGLE_APIS_KEY: Optional[str] = os.getenv("GOOGLE_APIS_KEY")
    FIRECRAWL_API_KEY: Optional[str] = os.getenv("FIRECRAWL_API_KEY")
    
config = Config()

import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class SourceIdentifier:
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
    async def check_url_safety(url: str) -> Optional[Dict[str, Any]]:
        """
        Check the safety of a URL using Google's Safe Browsing API.
        """
        api_key = config.GOOGLE_APIS_KEY
        if not api_key:
            logger.error("No Google API key provided.")
            return {"safe": "unknown", "status": "No API key provided"}
        
        api_url = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={api_key}"
        payload = {
            "client": {"clientId": "verifacts-backend", "clientVersion": "1.0.0"},
            "threatInfo": {
                "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"],
                "platformTypes": ["ANY_PLATFORM"],
                "threatEntryTypes": ["URL"],
                "threatEntries": [{"url": url}]
            }
        }
        try: 
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload) as response:
                    if response.status != 200:
                        logger.error(f"Google Safe Browsing API error: {response.status}")
                        return {"safe": "unknown", "status": f"API error: {response.status}"}
                    data = await response.json()
                    logger.info(f"Safe Browsing API response data: {data}")
                    if not data:
                        return {"safe": True, "status": "No threats found"}
                    
                    matches = data.get("matches", [])
                    logger.info(f"Threat matches: {matches}")
                    if matches:
                        threat_type = matches[0].get("threatType", "unknown")
                        return {"safe": False, "status": f"threat_type: {threat_type}", "threat": matches}
        except Exception as e:
            logger.error(f"Error checking URL safety: {e}")
            return {"safe": "unknown", "status": str(e)}
    
    @staticmethod
    async def get_whois_data(domain: str) -> Optional[Dict[str, Any]]:
        """
        Get WHOIS data for a given domain.
        """
        try:
            w = whois.whois(domain)
            logger.info(f"WHOIS data for {domain}: {w}")
            creation_date = w.creation_date
            if isinstance(creation_date, list):
                creation_date = creation_date[0]
                
            if not creation_date:
                logger.warning(f"No creation date found for domain: {domain}")
                return {"error": "No creation date found", "age_days": 0}

            now = datetime.datetime.now()
            if isinstance(creation_date, str):
                try:
                    creation_date = datetime.datetime.strptime(creation_date, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    logger.warning(f"Unable to parse creation date string: {creation_date}")
                    return {"error": "Invalid creation date format", "age_days": 0, "status": "unknown"}
                
            age_days = (now - creation_date).days
            logger.info(f"Domain {domain} age in days: {age_days}")
            return {
                "registrar": w.registrar,
                "creation_date": str(creation_date),
                "age_days": age_days,
                "org": w.org,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Error fetching WHOIS data for {domain}: {e}")
            return {"error": str(e), "age_days": 0, "status": "error"}
        
    @staticmethod
    async def get_ssl_history(domain: str) -> Optional[Dict[str, Any]]:
        """
        Get SSL certificate history using crt.sh for a given domain.
        """
        url = f"https://crt.sh/?q=%25.{domain}&output=json"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"crt.sh API error: {response.status}")
                        return {"error": f"API error: {response.status}", "status": "error"}
                    
                    data = await response.json()
                    if not data:
                        logger.info(f"No SSL certificate data found for domain: {domain}")
                        return {"history_years": 0,"certificates": [], "status": "no_data"}
                    logger.info(f"crt.sh data for {domain}: {data}")
                    
                    timestamps = []
                    for entry in data:
                        ts = entry.get("entry_timestamp")
                        if ts:
                            try:
                                dt = datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S")
                                timestamps.append(dt)
                            except ValueError:
                                logger.warning(f"Unable to parse timestamp: {ts}")
                    
                    if not timestamps:
                        logger.info(f"No valid timestamps found for domain: {domain}")
                        return {"history_years": 0, "certificates": data, "status": "no_valid_timestamps"}
                    
                    timestamps.sort()
                    earliest = timestamps[0]
                    earliest_dt = datetime.datetime.strptime(earliest, "%Y-%m-%d %H:%M:%S")
                    years_active = (datetime.datetime.now() - earliest_dt).days / 365
                    
                    return {
                        "history_years": round(years_active, 2),
                        "first_seen": str(earliest_dt),
                        "certificates": data,
                        "status": "success"
                    }
        except Exception as e:
            logger.error(f"Error fetching SSL history for {domain}: {e}")
            return {"error": str(e), "status": "error"}


# Example usage:
async def main():
    url = "https://www.databackedafrica.com/"
    identifier = SourceIdentifier()
    
    domain = identifier.extract_domain(url)
    whois_data = await identifier.get_whois_data(domain)
    ssl_history = await identifier.get_ssl_history(domain)
    url_safety = await identifier.check_url_safety(url)
    
    result = {
        "domain": domain,
        "whois_data": whois_data,
        "ssl_history": ssl_history,
        "url_safety": url_safety
    }
    
    print(result)
    
if __name__ == "__main__":
    import asyncio
    asyncio.run(main())