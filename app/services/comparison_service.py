"""Comparison service for comparing SHL assessments."""

import json
from pathlib import Path

from app.services.groq_service import generate_response
from app.utils.validators import get_catalog_item_by_name
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _load_prompt(filename: str) -> str:
    """Load a prompt template."""
    path = Path(__file__).parent.parent / "prompts" / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def find_assessments_to_compare(text: str) -> list[dict]:
    """Find assessment names mentioned in user text for comparison.

    Args:
        text: User message text.

    Returns:
        List of catalog items found.
    """
    text_lower = text.lower()

    # Known assessment short names to search for
    known_names = {
        "opq": "Occupational Personality Questionnaire (OPQ32)",
        "opq32": "Occupational Personality Questionnaire (OPQ32)",
        "verify": "SHL Verify G+ (General Ability)",
        "verify g+": "SHL Verify G+ (General Ability)",
        "numerical": "SHL Verify Numerical Reasoning",
        "verbal": "SHL Verify Verbal Reasoning",
        "deductive": "SHL Verify Deductive Reasoning",
        "inductive": "SHL Verify Inductive Reasoning",
        "mq": "Motivational Questionnaire (MQ)",
        "motivational": "Motivational Questionnaire (MQ)",
        "sjt": "Graduate Situational Judgment Test",
        "situational judgment": "Graduate Situational Judgment Test",
        "coding": "SHL Coding Simulations",
        "coding simulation": "SHL Coding Simulations",
        "360": "SHL 360-Degree Feedback",
        "video interview": "SHL Video Interview",
        "jfa": "Job-Focused Assessments (JFA)",
        "job focused": "Job-Focused Assessments (JFA)",
        "call center": "SHL Call Center Simulations",
        "language": "SHL Language Evaluation",
        "mechanical": "SHL Mechanical Comprehension Test",
        "checking": "SHL Checking Test (Attention to Detail)",
        "business skills": "SHL Business Skills Assessments",
        "technical skills": "SHL Technical Skills Assessments",
        "gsa": "SHL Verify G+ (General Ability)",
    }

    found = []
    seen = set()

    for short_name, full_name in known_names.items():
        if short_name in text_lower and full_name not in seen:
            item = get_catalog_item_by_name(full_name)
            if item:
                found.append(item)
                seen.add(full_name)

    return found


async def compare_assessments(text: str) -> str:
    """Generate a grounded comparison between mentioned assessments.

    Args:
        text: User message requesting comparison.

    Returns:
        Comparison summary text.
    """
    items = find_assessments_to_compare(text)

    if len(items) < 2:
        return (
            "I'd be happy to compare SHL assessments for you. "
            "Could you specify which two assessments you'd like to compare? "
            "For example: 'Compare OPQ and Verify G+' or 'What's the difference between SJT and OPQ?'"
        )

    # Build comparison data from catalog (grounded)
    comparison_data = []
    for item in items[:3]:  # Max 3 assessments to compare
        comparison_data.append(
            f"**{item['name']}**\n"
            f"- Type: {item['assessment_type']}\n"
            f"- Description: {item['description']}\n"
            f"- Skills measured: {', '.join(item.get('skills', []))}\n"
            f"- Tags: {', '.join(item.get('tags', []))}"
        )

    system_prompt = _load_prompt("system_prompt.txt")
    comparison_prompt = _load_prompt("comparison_prompt.txt")

    data_text = "\n\n".join(comparison_data)

    user_prompt = comparison_prompt.format(
        assessment_data=data_text,
        user_question=text,
    ) if comparison_prompt else (
        f"Compare the following SHL assessments based ONLY on the provided data:\n\n"
        f"{data_text}\n\n"
        f"User question: {text}\n\n"
        f"Provide a clear, structured comparison highlighting key differences and "
        f"when to use each assessment. Use ONLY the data provided above."
    )

    summary = await generate_response(system_prompt, user_prompt, max_tokens=768)

    logger.info("Generated comparison for %d assessments", len(items))
    return summary
