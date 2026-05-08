"""Ingest catalog.json into ChromaDB with embeddings.

Always clears existing data before re-ingesting to prevent stale items.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.retrieval.chroma_client import get_chroma_client, get_collection, reset_collection, COLLECTION_NAME
from app.utils.logger import get_logger

logger = get_logger(__name__)


def main():
    """Run catalog ingestion with forced rebuild."""
    logger.info("Starting catalog ingestion...")

    # Force-clear any existing collection to prevent stale data
    logger.info("Clearing existing collection to prevent stale items...")
    reset_collection()

    # Re-create and ingest (get_collection auto-ingests when empty)
    collection = get_collection()
    count = collection.count()
    logger.info("Ingestion complete. Collection has %d documents.", count)


if __name__ == "__main__":
    main()
