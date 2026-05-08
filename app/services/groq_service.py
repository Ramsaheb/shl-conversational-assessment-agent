"""Groq LLM service for natural language generation."""

from groq import Groq
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_client: Groq | None = None


def _get_client() -> Groq:
    """Get or initialize the Groq client."""
    global _client
    if _client is None:
        _client = Groq(api_key=settings.groq_api_key)
    return _client


async def generate_response(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1024,
    temperature: float = 0.3,
) -> str:
    """Generate a response using the Groq LLM.

    Args:
        system_prompt: System-level instructions.
        user_prompt: User message / context.
        max_tokens: Maximum tokens in the response.
        temperature: Sampling temperature (lower = more deterministic).

    Returns:
        Generated text response.
    """
    try:
        client = _get_client()

        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=0.9,
        )

        result = response.choices[0].message.content.strip()
        logger.info("Groq response generated (%d chars)", len(result))
        return result

    except Exception as e:
        logger.error("Groq API error: %s", str(e))
        # Return a safe fallback
        return "I'd be happy to help you find the right SHL assessments. Could you tell me more about the role you're hiring for?"
