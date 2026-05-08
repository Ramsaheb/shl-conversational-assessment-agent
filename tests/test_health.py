"""Tests for the health endpoint."""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_returns_200():
    """GET /health should return 200 with status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "ok"}


def test_health_response_schema():
    """Health response should have exactly one field: status."""
    response = client.get("/health")
    data = response.json()
    assert list(data.keys()) == ["status"]
    assert isinstance(data["status"], str)
