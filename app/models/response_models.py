"""Response models for the chat API."""

from pydantic import BaseModel, Field


class Recommendation(BaseModel):
    """A single SHL assessment recommendation."""

    name: str = Field(..., description="Assessment name")
    url: str = Field(..., description="Assessment URL on shl.com")
    test_type: str = Field(..., description="Type of assessment")


class ChatResponse(BaseModel):
    """Response body for the POST /chat endpoint."""

    reply: str = Field(..., description="Agent's conversational reply")
    recommendations: list[Recommendation] = Field(
        default_factory=list,
        description="List of recommended assessments (empty when clarifying or refusing)",
    )
    end_of_conversation: bool = Field(
        default=False,
        description="Whether the conversation has reached a natural end",
    )
