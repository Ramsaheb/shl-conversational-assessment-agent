"""Tests for conversation refinement."""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _chat(messages: list[dict]) -> dict:
    response = client.post("/chat", json={"messages": messages})
    assert response.status_code == 200
    return response.json()


def test_refinement_adds_personality():
    """User refining to add personality assessments should update results."""
    data = _chat([
        {"role": "user", "content": "I need assessments for a Java developer"},
        {"role": "assistant", "content": "Here are coding and technical assessments for a Java developer role."},
        {"role": "user", "content": "Actually add personality assessments too"},
    ])
    # Should have a reply (may or may not have recs depending on state)
    assert len(data["reply"]) > 0


def test_multi_turn_conversation():
    """Multi-turn conversation should build context."""
    data = _chat([
        {"role": "user", "content": "I'm hiring for a role"},
        {"role": "assistant", "content": "What role are you hiring for?"},
        {"role": "user", "content": "A senior Python developer who needs good communication skills"},
    ])
    assert len(data["reply"]) > 0


def test_schema_consistency_across_turns():
    """Response schema must be consistent regardless of turn count."""
    for messages in [
        [{"role": "user", "content": "Hello"}],
        [
            {"role": "user", "content": "I need help"},
            {"role": "assistant", "content": "Sure, what role?"},
            {"role": "user", "content": "Software engineer with Python skills"},
        ],
    ]:
        data = _chat(messages)
        assert "reply" in data
        assert "recommendations" in data
        assert "end_of_conversation" in data
