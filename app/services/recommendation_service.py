"""Recommendation service — retrieves and formats assessment recommendations."""

import json
from pathlib import Path

from app.retrieval.retriever import hybrid_retrieve
from app.retrieval.ranking import rank_results
from app.services.groq_service import generate_response
from app.models.response_models import Recommendation
from app.utils.validators import validate_recommendations
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _load_prompt(filename: str) -> str:
    """Load a prompt template from the prompts directory."""
    path = Path(__file__).parent.parent / "prompts" / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


async def get_recommendations(
    search_query: str,
    state: dict,
    top_k: int = 5,
) -> tuple[list[Recommendation], str]:
    """Retrieve and format assessment recommendations.

    Args:
        search_query: Search query built from conversation state.
        state: Extracted conversation state.
        top_k: Number of recommendations to return.

    Returns:
        Tuple of (recommendations list, summary text).
    """
    # Determine preferred assessment types from state
    preferred_types = []
    if state.get("needs_cognitive"):
        preferred_types.append("Cognitive")
    if state.get("needs_personality"):
        preferred_types.append("Personality")
    if state.get("needs_technical"):
        preferred_types.append("Skills & Simulations")
    if state.get("needs_behavioral"):
        preferred_types.append("Behavioral")

    # Retrieve candidates
    items = hybrid_retrieve(search_query, n_results=20)

    if not items:
        return [], "I couldn't find matching assessments for your criteria. Could you provide more details?"

    # Rank and select top-K
    ranked = rank_results(items, top_k=top_k, preferred_types=preferred_types)

    # Build recommendations from ranked results
    recommendations = []
    assessment_details = []

    for item in ranked:
        meta = item.get("metadata", {})
        name = meta.get("name", "Unknown")
        url = meta.get("url", "")
        atype = meta.get("assessment_type", "General")
        desc = meta.get("description", "")

        recommendations.append(Recommendation(
            name=name,
            url=url,
            test_type=atype,
        ))

        assessment_details.append(
            f"- {name} ({atype}): {desc}"
        )

    # Validate against catalog
    recommendations = validate_recommendations(recommendations)

    if not recommendations:
        return [], "I couldn't match your requirements to specific assessments. Could you clarify what type of role you're hiring for?"

    # Generate natural language summary using LLM
    system_prompt = _load_prompt("system_prompt.txt")
    rec_prompt = _load_prompt("recommendation_prompt.txt")

    context = {
        "role": state.get("role", "Not specified"),
        "seniority": state.get("seniority", "Not specified"),
        "skills": ", ".join(state.get("skills", [])) or "Not specified",
        "assessment_details": "\n".join(assessment_details),
        "num_recommendations": len(recommendations),
    }

    user_prompt = rec_prompt.format(**context) if rec_prompt else (
        f"The user is hiring for: {context['role']} ({context['seniority']}).\n"
        f"Required skills: {context['skills']}.\n\n"
        f"Based on the SHL catalog, here are the matching assessments:\n"
        f"{context['assessment_details']}\n\n"
        f"Provide a brief, professional summary explaining why these {context['num_recommendations']} "
        f"assessments are recommended for this role. Be concise."
    )

    summary = await generate_response(system_prompt, user_prompt, max_tokens=512)

    logger.info("Generated %d recommendations for query: %s",
                len(recommendations), search_query[:50])

    return recommendations, summary
