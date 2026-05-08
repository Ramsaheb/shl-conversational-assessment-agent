"""Tests for assessment comparison."""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _chat(messages: list[dict]) -> dict:
    response = client.post("/chat", json={"messages": messages})
    assert response.status_code == 200
    return response.json()


def test_comparison_opq_vs_verify():
    """Should compare OPQ and Verify assessments."""
    data = _chat([
        {"role": "user", "content": "What is the difference between OPQ and Verify G+?"}
    ])
    assert len(data["reply"]) > 50  # Should have substantial comparison
    assert data["recommendations"] == []  # Comparisons don't return recs


def test_comparison_returns_empty_recommendations():
    """Comparison responses should not include recommendations."""
    data = _chat([
        {"role": "user", "content": "Compare coding simulations vs technical skills assessments"}
    ])
    assert data["recommendations"] == []
