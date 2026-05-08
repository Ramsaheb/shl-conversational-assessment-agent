"""Ranking and scoring for retrieved assessments."""

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Scoring weights
SEMANTIC_WEIGHT = 0.6
KEYWORD_WEIGHT = 0.3
METADATA_WEIGHT = 0.1


def compute_combined_score(item: dict, preferred_types: list[str] | None = None) -> float:
    """Compute a combined relevance score for a retrieved item.

    Args:
        item: Retrieved item with semantic_score and keyword_score.
        preferred_types: Optional list of preferred type codes (e.g., ["A", "P"]) for boost.

    Returns:
        Combined score between 0 and 1.
    """
    semantic = item.get("semantic_score", 0.0)
    keyword = item.get("keyword_score", 0.0)

    # Metadata bonus: boost if assessment type matches preferred types
    metadata_bonus = 0.0
    if preferred_types:
        test_type = item.get("metadata", {}).get("test_type", "")
        # Check if ANY of the item's type codes match ANY preferred type
        for code in test_type:
            if code in preferred_types:
                metadata_bonus = 1.0
                break

    score = (
        SEMANTIC_WEIGHT * semantic
        + KEYWORD_WEIGHT * keyword
        + METADATA_WEIGHT * metadata_bonus
    )

    return min(score, 1.0)


def rank_results(
    items: list[dict],
    top_k: int = 10,
    preferred_types: list[str] | None = None,
) -> list[dict]:
    """Rank retrieved items by combined score and return top-K.

    Args:
        items: List of retrieved items.
        top_k: Number of top results to return.
        preferred_types: Optional preferred type codes (e.g., ["A", "P", "K"]).

    Returns:
        Top-K items sorted by descending combined score.
    """
    for item in items:
        item["combined_score"] = compute_combined_score(item, preferred_types)

    # Sort by combined score descending
    ranked = sorted(items, key=lambda x: x["combined_score"], reverse=True)

    # Deduplicate by assessment name
    seen_names = set()
    unique = []
    for item in ranked:
        name = item.get("metadata", {}).get("name", "")
        if name.lower() not in seen_names:
            seen_names.add(name.lower())
            unique.append(item)

    result = unique[:top_k]

    logger.info(
        "Ranked %d items -> top %d unique results",
        len(items), len(result)
    )

    return result
