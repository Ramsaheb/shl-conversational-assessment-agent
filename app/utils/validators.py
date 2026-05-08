"""Validators to ensure catalog-grounded responses."""

import json
from pathlib import Path
from app.models.response_models import Recommendation
from app.utils.logger import get_logger

logger = get_logger(__name__)

_catalog_cache: dict | None = None


def _load_catalog() -> dict:
    """Load and cache catalog data keyed by lowercase name."""
    global _catalog_cache
    if _catalog_cache is None:
        catalog_path = Path(__file__).parent.parent / "data" / "catalog.json"
        with open(catalog_path, "r", encoding="utf-8") as f:
            items = json.load(f)
        _catalog_cache = {}
        for item in items:
            _catalog_cache[item["name"].lower()] = item
            # Also index by id for convenience
            _catalog_cache[item["id"].lower()] = item
    return _catalog_cache


def validate_recommendations(recommendations: list[Recommendation]) -> list[Recommendation]:
    """Validate that all recommendations exist in the catalog.

    Removes any hallucinated assessments not in catalog.json.
    Enforces 1-10 recommendation limit.

    Args:
        recommendations: List of recommendations to validate.

    Returns:
        Validated list with only catalog-grounded recommendations.
    """
    catalog = _load_catalog()
    validated = []

    for rec in recommendations:
        name_lower = rec.name.lower()
        # Try exact match first
        if name_lower in catalog:
            item = catalog[name_lower]
            validated.append(Recommendation(
                name=item["name"],
                url=item["url"],
                test_type=item["assessment_type"],
            ))
        else:
            # Try partial match
            matched = False
            for cat_name, item in catalog.items():
                if name_lower in cat_name or cat_name in name_lower:
                    validated.append(Recommendation(
                        name=item["name"],
                        url=item["url"],
                        test_type=item["assessment_type"],
                    ))
                    matched = True
                    break
            if not matched:
                logger.warning("Filtered out non-catalog recommendation: %s", rec.name)

    # Enforce limit
    if len(validated) > 10:
        validated = validated[:10]

    return validated


def get_catalog_item_by_name(name: str) -> dict | None:
    """Look up a catalog item by name (case-insensitive, partial match)."""
    catalog = _load_catalog()

    name_lower = name.lower().strip()

    # Exact match
    if name_lower in catalog:
        return catalog[name_lower]

    # Partial match
    for cat_name, item in catalog.items():
        if name_lower in cat_name or cat_name in name_lower:
            return item

    return None


def get_all_catalog_items() -> list[dict]:
    """Get all catalog items as a list."""
    catalog_path = Path(__file__).parent.parent / "data" / "catalog.json"
    with open(catalog_path, "r", encoding="utf-8") as f:
        return json.load(f)
