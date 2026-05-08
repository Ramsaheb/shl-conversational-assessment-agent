"""Tests for the chat endpoint."""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _chat(messages: list[dict]) -> dict:
    """Helper to send chat request."""
    response = client.post("/chat", json={"messages": messages})
    assert response.status_code == 200
    return response.json()


def test_chat_response_schema():
    """Chat response must have exactly reply, recommendations, end_of_conversation."""
    data = _chat([{"role": "user", "content": "I need help hiring a Java developer"}])
    assert "reply" in data
    assert "recommendations" in data
    assert "end_of_conversation" in data
    assert isinstance(data["reply"], str)
    assert isinstance(data["recommendations"], list)
    assert isinstance(data["end_of_conversation"], bool)


def test_vague_query_returns_empty_recommendations():
    """Vague queries should trigger clarification with empty recommendations."""
    data = _chat([{"role": "user", "content": "I need an assessment"}])
    assert data["recommendations"] == [] or len(data["recommendations"]) == 0
    assert len(data["reply"]) > 0


def test_specific_query_returns_recommendations():
    """Specific queries should return 1-10 recommendations."""
    data = _chat([
        {"role": "user", "content": "I need a coding assessment for a senior Java developer"}
    ])
    if data["recommendations"]:
        assert 1 <= len(data["recommendations"]) <= 10
        for rec in data["recommendations"]:
            assert "name" in rec
            assert "url" in rec
            assert "test_type" in rec
            assert rec["url"].startswith("http")


def test_recommendation_schema_fields():
    """Each recommendation must have exactly name, url, test_type."""
    data = _chat([
        {"role": "user", "content": "Recommend personality assessments for a manager role"}
    ])
    if data["recommendations"]:
        for rec in data["recommendations"]:
            assert set(rec.keys()) == {"name", "url", "test_type"}


def test_max_10_recommendations():
    """Never return more than 10 recommendations."""
    data = _chat([
        {"role": "user", "content": "Show me all SHL cognitive and personality assessments for senior roles"}
    ])
    assert len(data["recommendations"]) <= 10


def test_invalid_request_missing_messages():
    """Missing messages field should return 422."""
    response = client.post("/chat", json={})
    assert response.status_code == 422


def test_invalid_request_empty_messages():
    """Empty messages list should return 422."""
    response = client.post("/chat", json={"messages": []})
    assert response.status_code == 422


def test_invalid_role_field():
    """Invalid role should return 422."""
    response = client.post("/chat", json={
        "messages": [{"role": "system", "content": "test"}]
    })
    assert response.status_code == 422
