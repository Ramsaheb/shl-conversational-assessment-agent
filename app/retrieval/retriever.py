"""Hybrid retrieval: semantic + keyword scoring. No hard metadata filtering."""

import json
from app.retrieval.chroma_client import get_collection
from app.retrieval.embedding_service import encode_text
from app.utils.logger import get_logger

logger = get_logger(__name__)


def semantic_search(query: str, n_results: int = 30) -> list[dict]:
    """Perform semantic similarity search using ChromaDB.

    Always retrieves broadly without metadata filters to maximize recall.

    Args:
        query: Search query text.
        n_results: Maximum number of results.

    Returns:
        List of result dicts with metadata and distance scores.
    """
    collection = get_collection()
    query_embedding = encode_text(query)

    n = min(n_results, collection.count())
    if n == 0:
        return []

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n,
        include=["documents", "metadatas", "distances"],
    )

    items = []
    if results and results["ids"] and results["ids"][0]:
        for i, doc_id in enumerate(results["ids"][0]):
            metadata = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 1.0
            # ChromaDB returns L2 distance; convert to similarity score (0-1)
            similarity = max(0, 1 - distance / 2)
            items.append({
                "id": doc_id,
                "document": results["documents"][0][i] if results["documents"] else "",
                "metadata": metadata,
                "semantic_score": similarity,
            })

    return items


def keyword_search(query: str, items: list[dict]) -> list[dict]:
    """Add keyword overlap scores to retrieved items.

    Uses Jaccard similarity between query tokens and item keywords/tags/skills.

    Args:
        query: Search query text.
        items: List of items from semantic search.

    Returns:
        Items with added keyword_score field.
    """
    query_tokens = set(query.lower().split())
    stop_words = {"i", "a", "an", "the", "is", "are", "was", "were", "for", "to",
                  "in", "on", "of", "and", "or", "not", "with", "need", "want",
                  "looking", "help", "me", "my", "can", "you", "do", "what", "how"}
    query_tokens -= stop_words

    if not query_tokens:
        for item in items:
            item["keyword_score"] = 0.0
        return items

    for item in items:
        meta = item.get("metadata", {})
        item_tokens = set()

        name = meta.get("name", "").lower().split()
        item_tokens.update(name)

        for field in ["keywords", "tags", "skills"]:
            raw = meta.get(field, "[]")
            try:
                values = json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(values, list):
                    for v in values:
                        item_tokens.update(str(v).lower().split())
            except (json.JSONDecodeError, TypeError):
                pass

        # Jaccard similarity
        if item_tokens:
            intersection = query_tokens & item_tokens
            union = query_tokens | item_tokens
            item["keyword_score"] = len(intersection) / len(union) if union else 0.0
        else:
            item["keyword_score"] = 0.0

    return items


def hybrid_retrieve(
    query: str,
    n_results: int = 30,
    assessment_types: list[str] | None = None,
) -> list[dict]:
    """Perform hybrid retrieval combining semantic search and keyword matching.

    IMPORTANT: We never hard-filter by assessment type. Instead, type preference
    is passed through to the ranking layer as a boosting signal. This maximizes
    recall, which is the primary evaluation metric.

    Args:
        query: Search query text.
        n_results: Maximum number of results.
        assessment_types: Optional types for ranking boost (NOT for filtering).

    Returns:
        List of retrieved items with combined scores, sorted by relevance.
    """
    # Step 1: Broad semantic search (no where filter)
    items = semantic_search(query, n_results=n_results)

    if not items:
        logger.warning("No results from semantic search for query: %s", query)
        return []

    # Step 2: Add keyword scores
    items = keyword_search(query, items)

    # Pass type preferences through as metadata for ranking
    if assessment_types:
        for item in items:
            item["preferred_types"] = assessment_types

    logger.info(
        "Hybrid retrieval returned %d items for query: '%s'",
        len(items), query[:50]
    )

    return items
