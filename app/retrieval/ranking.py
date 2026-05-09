"""Ranking and scoring for retrieved assessments."""

import re
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Scoring weights
SEMANTIC_WEIGHT = 0.6
KEYWORD_WEIGHT = 0.3
METADATA_WEIGHT = 0.1

# Technical domain keywords that should only appear in results
# if they were explicitly part of the user's query
TECH_DOMAIN_KEYWORDS = {
    "java", "python", "c#", ".net", "dotnet", "c++", "cpp", "ruby",
    "javascript", "typescript", "php", "swift", "kotlin", "rust", "go",
    "golang", "scala", "perl", "html", "css", "react", "angular", "vue",
    "node", "django", "flask", "spring", "hibernate", "microservices",
    "docker", "kubernetes", "aws", "azure", "gcp", "sql", "nosql",
    "mongodb", "oracle", "sap", "salesforce", "hadoop", "spark",
    "tableau", "power bi", "autocad", "solidworks",
}


def _compute_name_penalty(item: dict, query: str) -> float:
    """Penalize items whose names contain tech domain keywords not in the query.

    Returns a penalty between 0.0 (no penalty) and 0.4 (heavy penalty).
    """
    query_lower = query.lower()
    name_lower = item.get("metadata", {}).get("name", "").lower()

    penalty = 0.0
    for tech_kw in TECH_DOMAIN_KEYWORDS:
        if tech_kw in name_lower and tech_kw not in query_lower:
            penalty = 0.4
            break

    return penalty


def compute_combined_score(
    item: dict,
    preferred_types: list[str] | None = None,
    query: str = "",
) -> float:
    """Compute a combined relevance score for a retrieved item.

    Args:
        item: Retrieved item with semantic_score and keyword_score.
        preferred_types: Optional list of preferred type codes (e.g., ["A", "P"]) for boost.
        query: Original search query for name-relevance penalty.

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

    # Apply name-relevance penalty for domain mismatch
    if query:
        score -= _compute_name_penalty(item, query)

    return max(min(score, 1.0), 0.0)


def rank_results(
    items: list[dict],
    top_k: int = 10,
    preferred_types: list[str] | None = None,
    query: str = "",
) -> list[dict]:
    """Rank retrieved items by combined score and return top-K.

    Args:
        items: List of retrieved items.
        top_k: Number of top results to return.
        preferred_types: Optional preferred type codes (e.g., ["A", "P", "K"]).
        query: Original search query for relevance penalty.

    Returns:
        Top-K items sorted by descending combined score.
    """
    for item in items:
        item["combined_score"] = compute_combined_score(item, preferred_types, query)

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

