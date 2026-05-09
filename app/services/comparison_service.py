"""Comparison service for comparing SHL assessments."""

import json
import re
from pathlib import Path

from app.services.groq_service import generate_response
from app.utils.validators import get_catalog_item_by_name, get_all_catalog_items
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
    items = get_all_catalog_items()

    # Well-known abbreviation → catalog name fragment mapping
    COMMON_ALIASES = {
        "opq": "occupational personality questionnaire",
        "opq32": "occupational personality questionnaire",
        "opq32r": "occupational personality questionnaire",
        "verify g+": "verify g+",
        "verify g": "verify g+",
        "mq": "motivational questionnaire",
        "sjt": "situational judgement",
        "cebshl": "ceb",
    }

    found = []
    seen = set()

    # First pass: match common abbreviations from user text
    for alias, fragment in COMMON_ALIASES.items():
        if alias in text_lower:
            # Find the first catalog item whose name contains the fragment
            for item in items:
                if fragment in item["name"].lower() and item["name"] not in seen:
                    found.append(item)
                    seen.add(item["name"])
                    break  # One match per alias

    # Second pass: match full or partial catalog names directly in user text
    for item in items:
        if item["name"] in seen:
            continue
        name_lower = item["name"].lower()
        aliases = [name_lower]

        if name_lower.startswith("shl "):
            aliases.append(name_lower[4:])

        import re
        match = re.search(r'\(([^)]+)\)', name_lower)
        if match:
            acronym = match.group(1).strip()
            aliases.append(acronym)
            aliases.append(re.sub(r'\([^)]+\)', '', name_lower).strip())

        for alias in aliases:
            if len(alias) >= 3 and alias in text_lower and item["name"] not in seen:
                found.append(item)
                seen.add(item["name"])
                break

    return found


def _extract_requested_assessments(text: str) -> list[str]:
    """Extract assessment-like tokens from a comparison request."""
    text_clean = re.sub(r"[?.!]", "", text.lower()).strip()

    match = re.search(r"compare\s+(.+?)\s+(?:and|vs|versus)\s+(.+)", text_clean)
    if not match:
        match = re.search(r"(.+?)\s+(?:vs|versus)\s+(.+)", text_clean)

    if not match:
        return []

    left = match.group(1).strip()
    right = match.group(2).strip()

    def _trim_suffix(s: str) -> str:
        # Remove trailing context like "for leadership roles"
        parts = re.split(r"\bfor\b|\bwhich\b|\bshould\b|\bused\b", s)
        return parts[0].strip()

    candidates = [_trim_suffix(left), _trim_suffix(right)]
    return [c for c in candidates if c]


async def compare_assessments(text: str) -> str:
    """Generate a grounded comparison between mentioned assessments.

    Args:
        text: User message requesting comparison.

    Returns:
        Comparison summary text.
    """
    items = find_assessments_to_compare(text)

    if len(items) < 2:
        requested = _extract_requested_assessments(text)
        if requested:
            missing = [r for r in requested if not get_catalog_item_by_name(r)]
            if missing:
                missing_text = ", ".join(missing)
                return (
                    f"I couldn't find {missing_text} in the SHL catalog. "
                    "Please provide the exact assessment names from the SHL catalog "
                    "so I can compare them accurately."
                )

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
            f"- Type: {item.get('test_type', 'K')}\n"
            f"- Description: {item.get('description', '')}\n"
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
