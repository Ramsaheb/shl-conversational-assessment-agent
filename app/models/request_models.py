"""Request models for the chat API."""

from pydantic import BaseModel, Field
from typing import Literal


class ChatMessage(BaseModel):
    """A single message in the conversation."""

    role: Literal["user", "assistant"] = Field(
        ..., description="The role of the message sender"
    )
    content: str = Field(
        ..., min_length=1, max_length=4000, description="The message content"
    )


class ChatRequest(BaseModel):
    """Request body for the POST /chat endpoint."""

    messages: list[ChatMessage] = Field(
        ..., min_length=1, max_length=50, description="Conversation history"
    )
