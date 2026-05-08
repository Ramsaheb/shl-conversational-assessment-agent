"""Embedding service using sentence-transformers."""

from sentence_transformers import SentenceTransformer
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """Get or initialize the embedding model (singleton)."""
    global _model
    if _model is None:
        logger.info("Loading embedding model: %s", settings.embedding_model)
        _model = SentenceTransformer(settings.embedding_model)
        logger.info("Embedding model loaded successfully")
    return _model


def encode_text(text: str) -> list[float]:
    """Encode text into an embedding vector.

    Args:
        text: Input text to encode.

    Returns:
        List of floats representing the embedding.
    """
    model = get_embedding_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def encode_texts(texts: list[str]) -> list[list[float]]:
    """Encode multiple texts into embedding vectors.

    Args:
        texts: List of input texts to encode.

    Returns:
        List of embedding vectors.
    """
    model = get_embedding_model()
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
    return embeddings.tolist()
