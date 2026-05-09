"""Recommendation service — retrieves and formats assessment recommendations."""

import json
import re
from pathlib import Path

from app.retrieval.retriever import hybrid_retrieve
from app.retrieval.ranking import rank_results
from app.services.groq_service import generate_response
from app.models.response_models import Recommendation
from app.utils.validators import validate_recommendations, get_all_catalog_items
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _sanitize_reply(text: str) -> str:
    """Remove any URLs from the LLM-generated reply text.

    This ensures the reply field never contains hallucinated links.
    Valid URLs are only in the structured recommendations array.
    """
    # Strip any http/https URLs
    text = re.sub(r'https?://\S+', '', text)
    # Clean up leftover artifacts like empty parentheses or brackets
    text = re.sub(r'\(\s*\)', '', text)
    text = re.sub(r'\[\s*\]', '', text)
    # Collapse multiple spaces
    text = re.sub(r'  +', ' ', text)
    return text.strip()


def _ground_reply(text: str, valid_recs: list[Recommendation]) -> str:
    """Ensure the LLM reply only mentions assessments in the validated shortlist.

    Two-layer grounding:
    1. Remove any catalog name that is NOT in the current shortlist.
    2. Detect hallucinated assessment-looking names (containing 'Assessment',
       'Test', 'Questionnaire', etc.) that don't exist in the catalog at all.
    """
    from app.utils.validators import get_all_catalog_items

    # Build whitelist of names that are in our recommendations
    rec_names_lower = {r.name.lower() for r in valid_recs}

    # Build a set of ALL catalog names
    all_catalog_items = get_all_catalog_items()
    all_catalog_names = {item["name"] for item in all_catalog_items}
    all_catalog_names_lower = {n.lower() for n in all_catalog_names}

    # Layer 1: Remove catalog names not in the shortlist
    for cat_name in all_catalog_names:
        if cat_name.lower() not in rec_names_lower and cat_name in text:
            text = text.replace(cat_name, "an additional assessment")

    # Layer 2: Detect hallucinated assessment-looking names
    # Match patterns like "SHL XYZ Assessment", "XYZ Test", "XYZ Questionnaire"
    hallucination_patterns = [
        r'(?:SHL\s+)?[A-Z][A-Za-z0-9\s&\-]+(?:Assessment|Test|Questionnaire|Inventory|Survey|Scale|Battery|Report)',
    ]
    for pattern in hallucination_patterns:
        for match in re.finditer(pattern, text):
            matched_name = match.group(0).strip()
            # Check if this is a recommended name or a known catalog name
            if (matched_name.lower() not in rec_names_lower and
                matched_name.lower() not in all_catalog_names_lower and
                matched_name not in all_catalog_names):
                # It's hallucinated — replace it
                text = text.replace(matched_name, "a relevant assessment")

    return text


def _load_prompt(filename: str) -> str:
    """Load a prompt template from the prompts directory."""
    path = Path(__file__).parent.parent / "prompts" / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


async def get_recommendations(
    search_query: str,
    state: dict,
    top_k: int = 7,
) -> tuple[list[Recommendation], str]:
    """Retrieve and format assessment recommendations.

    Args:
        search_query: Search query built from conversation state.
        state: Extracted conversation state.
        top_k: Number of recommendations to return.

    Returns:
        Tuple of (recommendations list, summary text).
    """
    # Determine preferred assessment types from state (for ranking boost, not filtering)
    preferred_types = []
    if state.get("needs_cognitive"):
        preferred_types.extend(["A"])  # Ability/Cognitive
    if state.get("needs_personality"):
        preferred_types.extend(["P"])  # Personality
    if state.get("needs_technical"):
        preferred_types.extend(["K", "S"])  # Knowledge, Simulation
    if state.get("needs_behavioral"):
        preferred_types.extend(["B"])  # Behavioral

    # Retrieve candidates (broad search, no hard filtering)
    items = hybrid_retrieve(search_query, n_results=30)

    if not items:
        return [], "I couldn't find matching assessments for your criteria. Could you provide more details?"

    # Rank and select top-K
    ranked = rank_results(items, top_k=top_k, preferred_types=preferred_types, query=search_query)

    # Build recommendations from ranked results
    recommendations = []
    assessment_details = []

    for item in ranked:
        meta = item.get("metadata", {})
        name = meta.get("name", "Unknown")
        url = meta.get("url", "")
        test_type = meta.get("test_type", "K")
        desc = meta.get("description", "")

        recommendations.append(Recommendation(
            name=name,
            url=url,
            test_type=test_type,
        ))

        assessment_details.append(
            f"- {name} (Type: {test_type}): {desc}"
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
        f"assessments are recommended for this role. Be concise. "
        f"IMPORTANT: Do NOT include any URLs in your summary."
    )

    summary = await generate_response(system_prompt, user_prompt, max_tokens=512)

    # Post-generation grounding: strip URLs + whitelist-check assessment names
    summary = _sanitize_reply(summary)
    summary = _ground_reply(summary, recommendations)

    logger.info("Generated %d recommendations for query: %s",
                len(recommendations), search_query[:50])

    return recommendations, summary
