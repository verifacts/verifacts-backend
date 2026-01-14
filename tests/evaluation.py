import requests
import csv
import json
import time
from datetime import datetime
from typing import List, Dict, Optional

API_URL = "https://verifacts-backend.onrender.com/api/v1/analyze"

# -----------------------------
# Evaluation Inputs
# -----------------------------
evaluation_inputs = [
  {
    "url": "https://www.snopes.com/list/2024-review-snopes/",
    "selection": "Aaron Rodgers faces a lifetime suspension from the NFL due to a suspiciously speedy recovery.",
    "expected_verdict": "False"
  },
  {
    "url": "https://www.snopes.com/list/2024-review-snopes/",
    "selection": "Caitlin Clark joined the U.S. Women’s National Team after Brittney Griner was released.",
    "expected_verdict": "False"
  },
  {
    "url": "https://www.snopes.com/list/2024-review-snopes/",
    "selection": "Papuan fisherman caught a giant axolotl sea creature.",
    "expected_verdict": "False"
  },
  {
    "url": "https://www.politifact.com/article/2023/dec/21/politifacts-15-most-popular-social-media-fact-chec/",
    "selection": "An Instagram video shows a man confronting President Joe Biden about an inappropriate relationship with a 13-year-old girl.",
    "expected_verdict": "False"
  },
  {
    "url": "https://www.politifact.com/article/2023/dec/21/politifacts-15-most-popular-social-media-fact-chec/",
    "selection": "The day before 9/11 the Pentagon reported $2.3 trillion missing.",
    "expected_verdict": "False"
  },
  {
    "url": "https://www.politifact.com/article/2023/dec/21/politifacts-15-most-popular-social-media-fact-chec/",
    "selection": "Bill Gates is coating organic produce with a dangerous chemical.",
    "expected_verdict": "False"
  },
  {
    "url": "https://www.politifact.com/article/2023/dec/21/politifacts-15-most-popular-social-media-fact-chec/",
    "selection": "Michelle Obama is a man.",
    "expected_verdict": "False"
  },
  {
    "url": "https://www.politifact.com/article/2023/dec/21/politifacts-15-most-popular-social-media-fact-chec/",
    "selection": "Elon Musk said a Tesla feature can scan testicles to start the car.",
    "expected_verdict": "False"
  },
  {
    "url": "https://www.politifact.com/article/2023/dec/21/politifacts-15-most-popular-social-media-fact-chec/",
    "selection": "MMA fighter Victoria Lee died because of a COVID-19 vaccine.",
    "expected_verdict": "False"
  },
  {
    "url": "https://www.politifact.com/factchecks/list/",
    "selection": "Video shows a leaked Donald Trump audio about the Epstein files and Venezuela.",
    "expected_verdict": "False"
  },
  {
    "url": "https://www.politifact.com/factchecks/list/",
    "selection": "Walmart’s 2025 Thanksgiving dinner costs show 25% reduction between Biden and Trump.",
    "expected_verdict": "False"
  },
  {
    "url": "https://www.politifact.com/factchecks/list/",
    "selection": "Voting in California is rigged.",
    "expected_verdict": "False"
  },
  {
    "url": "https://www.politifact.com/factchecks/list/",
    "selection": "The majority of Supplemental Nutrition Assistance Program recipients are not U.S. citizens.",
    "expected_verdict": "False"
  },
  {
    "url": "https://www.politifact.com/factchecks/list/",
    "selection": "Evidence suggests 1 in 25 women who consume abortion pills are hospitalized.",
    "expected_verdict": "False"
  },
  {
    "url": "https://en.wikipedia.org/wiki/Springfield_pet-eating_hoax",
    "selection": "Haitian immigrants were stealing and eating cats in Springfield, Ohio.",
    "expected_verdict": "False"
  }
]


# -----------------------------
# Output Files
# -----------------------------
CSV_FILE = "evaluation_results.csv"
JSON_FILE = "evaluation_results.json"

# -----------------------------
# Helper Functions
# -----------------------------
def call_verification_api(url: str, selection: Optional[str] = None) -> Dict:
    payload = {
        "url": url,
        "selection": selection,
        "force_refresh": False
    }

    start_time = time.time()
    response = requests.post(API_URL, json=payload)
    latency_ms = (time.time() - start_time) * 1000

    response.raise_for_status()
    data = response.json()

    return data, latency_ms


# -----------------------------
# Main Evaluation Loop
# -----------------------------
all_results = []

with open(CSV_FILE, mode="w", newline="", encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile)

    writer.writerow([
        "timestamp",
        "url",
        "input_mode",
        "claim_text",
        "claim_verdict",
        "confidence",
        "source_trust_level",
        "source_score",
        "verified_count",
        "debunked_count",
        "overall_verdict",
        "latency_ms",
        "evidence_sources"
    ])

    for item in evaluation_inputs:
        url = item["url"]
        selection = item.get("selection")
        input_mode = "selection" if selection else "extracted"

        try:
            result, latency = call_verification_api(url, selection)

            source_identity = result.get("source_identity", {})
            verdict_summary = result.get("verdict", {})
            claims = result.get("claims", [])

            for claim in claims:
                writer.writerow([
                    datetime.utcnow().isoformat(),
                    url,
                    input_mode,
                    claim.get("claim"),
                    claim.get("verdict"),
                    claim.get("confidence"),
                    source_identity.get("trust_level"),
                    source_identity.get("score"),
                    verdict_summary.get("verified_count"),
                    verdict_summary.get("debunked_count"),
                    verdict_summary.get("overall_verdict"),
                    round(latency, 2),
                    "; ".join(claim.get("sources", []))
                ])

            all_results.append({
                "url": url,
                "input_mode": input_mode,
                "latency_ms": latency,
                "api_response": result
            })

        except Exception as e:
            print(f"Error processing {url}: {e}")

# Save full JSON responses
with open(JSON_FILE, "w", encoding="utf-8") as f:
    json.dump(all_results, f, indent=2)

print("Evaluation completed.")
print(f"Results saved to {CSV_FILE} and {JSON_FILE}.")