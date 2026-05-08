"""Ingest catalog.json into ChromaDB with embeddings."""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.retrieval.chroma_client import get_collection
from app.utils.logger import get_logger

logger = get_logger(__name__)


def main():
    """Run catalog ingestion."""
    logger.info("Starting catalog ingestion...")
    collection = get_collection()  # Auto-ingests if empty
    count = collection.count()
    logger.info("Ingestion complete. Collection has %d documents.", count)


if __name__ == "__main__":
    main()
