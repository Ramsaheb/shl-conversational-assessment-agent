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


def get_collection() -> chromadb.Collection:
    """Get or create the SHL assessments collection.

    Auto-ingests catalog data if collection is empty.
    """
    global _collection
    if _collection is None:
        client = get_chroma_client()
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"description": "SHL assessment catalog embeddings"},
        )

        # Auto-ingest if empty
        if _collection.count() == 0:
            logger.info("Collection is empty, auto-ingesting catalog...")
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

    # Build composite text for embedding
    ids = []
    documents = []
    metadatas = []

    for item in catalog:
        item_id = item["id"]
        # Composite text: name + description + skills + tags for rich embedding
        composite = (
            f"{item['name']}. {item['description']}. "
            f"Skills: {', '.join(item.get('skills', []))}. "
            f"Tags: {', '.join(item.get('tags', []))}. "
            f"Keywords: {', '.join(item.get('keywords', []))}"
        )

        ids.append(item_id)
        documents.append(composite)
        metadatas.append({
            "name": item["name"],
            "url": item["url"],
            "description": item["description"],
            "assessment_type": item["assessment_type"],
            "skills": json.dumps(item.get("skills", [])),
            "tags": json.dumps(item.get("tags", [])),
            "keywords": json.dumps(item.get("keywords", [])),
        })

    # Generate embeddings
    embeddings = encode_texts(documents)

    # Upsert into ChromaDB
    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    logger.info("Successfully ingested %d items into ChromaDB", len(ids))


def get_catalog_lookup() -> dict[str, dict]:
    """Load catalog.json as a lookup dict keyed by assessment name (lowered)."""
    catalog_path = Path(__file__).parent.parent / "data" / "catalog.json"
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)
    return {item["name"].lower(): item for item in catalog}
