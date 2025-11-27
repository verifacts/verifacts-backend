import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from app.api.main import main

client = TestClient(main)


@pytest.fixture
def mock_graph_response():
    """
    Returns a fake state object that simulates a completed AI analysis.
    """
    return {
        "is_verified_entity": True,
        "identity_score": 0.85,
        "verdict_status": "Verified",
        "extracted_claims": ["Claim 1", "Claim 2"],
        "claims_verified_count": 2,
        "claims_sourced_count": 2,
        "verification_results": [{"claim": "Claim 1", "status": "True"}],
        "agent_reports": [
            {
                "agent_name": "Firecrawl Reader",
                "output": ["Claim 1", "Claim 2"],
                "errors": []
            }
        ]
    }
    
def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "version" in data == "`1.0.0`"
    
    
@patch("app.api.v1.endpoints.verifacts_pipeline.ainvoke", new_callable=AsyncMock)
def test_analyze_content(mock_ainvoke, mock_graph_response):
    """
    Test the /analyze endpoint with a mocked AI graph response.
    """
    mock_ainvoke.return_value = mock_graph_response

    request_payload = {
        "url": "https://example.com/article",
        "selection": None,
        "force_refresh": False
    }

    response = client.post("/api/v1/analyze", json=request_payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "Completed"
    assert data["verdict"]["status"] == "Verified"
    assert data["verdict"]["claims_verified"] == 2
    assert data["identity"]["verified"] is True
    assert data["identity"]["score"] == 0.85
    assert len(data["details"]["reports"]) == 1
    assert data["details"]["reports"][0]["agent"] == "Firecrawl Reader"
    
@patch("app.api.v1.endpoints.verifacts_pipeline.ainvoke", new_callable=AsyncMock)
def test_analyze_content_with_selection(mock_ainvoke, mock_graph_response):
    """
    Test the /analyze endpoint with a text selection and mocked AI graph response.
    """
    mock_ainvoke.return_value = mock_graph_response

    request_payload = {
        "url": "https://example.com/article",
        "selection": "Some specific text from the article.",
        "force_refresh": True
    }

    response = client.post("/api/v1/analyze", json=request_payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "Completed"
    assert data["verdict"]["status"] == "Verified"
    assert data["verdict"]["claims_verified"] == 2
    assert data["identity"]["verified"] is True
    assert data["identity"]["score"] == 0.85
    assert len(data["details"]["reports"]) == 1
    assert data["details"]["reports"][0]["agent"] == "Firecrawl Reader"
    
@patch("app.api.v1.endpoints.verifacts_pipeline.ainvoke", new_callable=AsyncMock)
def test_analyze_validation_error(mock_ainvoke):
    """
    Test the /analyze endpoint with invalid input to trigger validation error.
    """
    request_payload = {
        "url": "not_a_valid_url",
        "selection": None,
        "force_refresh": False
    }

    response = client.post("/api/v1/analyze", json=request_payload)
    assert response.status_code == 422  # Unprocessable Entity due to validation error