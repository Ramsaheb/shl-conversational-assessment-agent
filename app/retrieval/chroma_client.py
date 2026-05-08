"""ChromaDB client and collection management."""

import json
import os
import chromadb
from pathlib import Path

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_client: chromadb.ClientAPI | None = None
_collection: chromadb.Collection | None = None

COLLECTION_NAME = "shl_assessments"


def get_chroma_client() -> chromadb.ClientAPI:
    """Get or initialize the ChromaDB persistent client."""
    global _client
    if _client is None:
        persist_dir = settings.chroma_persist_dir
        os.makedirs(persist_dir, exist_ok=True)
        logger.info("Initializing ChromaDB at: %s", persist_dir)
        _client = chromadb.PersistentClient(path=persist_dir)
    return _client


def _get_catalog_count() -> int:
    """Get the number of items in catalog.json."""
    catalog_path = Path(__file__).parent.parent / "data" / "catalog.json"
    if catalog_path.exists():
        with open(catalog_path, "r", encoding="utf-8") as f:
            return len(json.load(f))
    return 0


def get_collection() -> chromadb.Collection:
    """Get or create the SHL assessments collection.

    Auto-ingests catalog data if collection is empty or stale.
    Detects stale index by comparing catalog item count vs ChromaDB count.
    """
    global _collection
    if _collection is None:
        client = get_chroma_client()
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"description": "SHL assessment catalog embeddings"},
        )

        db_count = _collection.count()
        catalog_count = _get_catalog_count()

        if db_count == 0:
            logger.info("Collection is empty, auto-ingesting catalog...")
            _ingest_catalog(_collection)
        elif db_count != catalog_count:
            logger.warning(
                "Stale index detected: ChromaDB has %d items, catalog has %d. Rebuilding...",
                db_count, catalog_count
            )
            # Delete and re-create
            client.delete_collection(COLLECTION_NAME)
            _collection = client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"description": "SHL assessment catalog embeddings"},
            )
            _ingest_catalog(_collection)

    return _collection


def _ingest_catalog(collection: chromadb.Collection) -> None:
    """Ingest the catalog.json into ChromaDB with embeddings."""
    from app.retrieval.embedding_service import encode_texts

    catalog_path = Path(__file__).parent.parent / "data" / "catalog.json"

    if not catalog_path.exists():
        logger.error("Catalog file not found at: %s", catalog_path)
        return

    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    logger.info("Ingesting %d catalog items...", len(catalog))

    ids = []
    documents = []
    metadatas = []
    seen_ids = set()

    for idx, item in enumerate(catalog):
        item_id = item["id"]
        # Ensure unique IDs
        if item_id in seen_ids:
            item_id = f"{item_id}_{idx}"
        seen_ids.add(item_id)
        # Composite text: name + description + keywords for rich embedding
        keywords = item.get("keywords", [])
        skills = item.get("skills", [])
        tags = item.get("tags", [])

        composite = (
            f"{item['name']}. {item.get('description', '')}. "
            f"Skills: {', '.join(skills) if isinstance(skills, list) else skills}. "
            f"Tags: {', '.join(tags) if isinstance(tags, list) else tags}. "
            f"Keywords: {', '.join(keywords) if isinstance(keywords, list) else keywords}"
        )

        ids.append(item_id)
        documents.append(composite)
        metadatas.append({
            "name": item["name"],
            "url": item["url"],
            "description": item.get("description", ""),
            "assessment_type": item.get("assessment_type", item.get("test_type", "K")),
            "test_type": item.get("test_type", "K"),
            "skills": json.dumps(skills) if isinstance(skills, list) else str(skills),
            "tags": json.dumps(tags) if isinstance(tags, list) else str(tags),
            "keywords": json.dumps(keywords) if isinstance(keywords, list) else str(keywords),
        })

    # Generate embeddings
    embeddings = encode_texts(documents)

    # Upsert in batches to avoid memory issues
    batch_size = 100
    for i in range(0, len(ids), batch_size):
        end = min(i + batch_size, len(ids))
        collection.upsert(
            ids=ids[i:end],
            documents=documents[i:end],
            embeddings=embeddings[i:end],
            metadatas=metadatas[i:end],
        )

    logger.info("Successfully ingested %d items into ChromaDB", len(ids))


def reset_collection() -> None:
    """Delete and re-create the collection (useful for re-ingestion)."""
    global _collection
    client = get_chroma_client()
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    _collection = None
    logger.info("Collection reset. Will re-ingest on next access.")
