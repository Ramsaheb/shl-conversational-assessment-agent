"""Chat API route."""

from fastapi import APIRouter, HTTPException

from app.models.request_models import ChatRequest
from app.models.response_models import ChatResponse, Recommendation
from app.services.conversation_service import process_conversation
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Process a conversation and return a response with optional recommendations.

    The agent analyzes the full conversation history to determine intent,
    then either asks clarifying questions, provides recommendations,
    compares assessments, or refuses off-topic requests.
    """
    try:
        logger.info(
            "Processing chat request with %d message(s)", len(request.messages)
        )

        response = await process_conversation(request.messages)

        # Validate response structure
        if response.recommendations:
            if len(response.recommendations) > 10:
                response.recommendations = response.recommendations[:10]
            logger.info(
                "Returning %d recommendation(s)", len(response.recommendations)
            )
        else:
            logger.info("Returning response without recommendations")

        return response

    except Exception as e:
        logger.error("Error processing chat request: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing your request. Please try again.",
        )
