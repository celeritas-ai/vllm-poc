"""Tests for the vLLM PoC application."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
import sys
import os

# Add the parent directory to the path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_llm_engine():
    """Mock the LLM engine for testing."""
    mock_engine = AsyncMock()
    mock_output = AsyncMock()
    mock_output.request_id = "test-123"
    mock_output.outputs = [AsyncMock()]
    mock_output.outputs[0].text = "Hello! How can I help you today?"
    
    async def mock_generate(*args, **kwargs):
        yield mock_output
    
    mock_engine.generate = mock_generate
    return mock_engine


class TestHealthEndpoint:
    """Test the health check endpoint."""
    
    def test_health_endpoint_without_model(self, client):
        """Test health endpoint when model is not loaded."""
        response = client.get("/health")
        assert response.status_code == 503
        assert "Model not loaded" in response.json()["detail"]


class TestModelsEndpoint:
    """Test the models listing endpoint."""
    
    def test_list_models(self, client):
        """Test the models endpoint."""
        response = client.get("/models")
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert len(data["data"]) > 0
        assert "id" in data["data"][0]


class TestChatEndpoint:
    """Test the chat completions endpoint."""
    
    @patch('app.llm_engine')
    def test_chat_completions_without_model(self, mock_engine, client):
        """Test chat endpoint when model is not loaded."""
        mock_engine = None
        
        response = client.post("/v1/chat/completions", json={
            "messages": [{"role": "user", "content": "Hello"}]
        })
        assert response.status_code == 503
        assert "Model not loaded" in response.json()["detail"]
    
    def test_chat_completions_invalid_request(self, client):
        """Test chat endpoint with invalid request."""
        response = client.post("/v1/chat/completions", json={
            "messages": "invalid"
        })
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__])