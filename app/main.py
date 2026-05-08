"""FastAPI application entry point."""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.utils.logger import get_logger
from app.routes.chat import router as chat_router
from app.retrieval.chroma_client import get_collection
from app.retrieval.embedding_service import get_embedding_model

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm up models and database on startup."""
    logger.info("Starting SHL Assessment Recommendation Agent...")

    # Warm up embedding model
    logger.info("Loading embedding model: %s", settings.embedding_model)
    get_embedding_model()
    logger.info("Embedding model loaded successfully")

    # Warm up ChromaDB collection
    logger.info("Initializing ChromaDB collection...")
    collection = get_collection()
    count = collection.count()
    logger.info("ChromaDB collection ready with %d documents", count)

    if count == 0:
        logger.warning(
            "ChromaDB collection is empty! Run 'python -m scripts.ingest_catalog' first."
        )

    yield

    logger.info("Shutting down SHL Assessment Recommendation Agent...")


app = FastAPI(
    title="SHL Assessment Recommendation Agent",
    description=(
        "A conversational AI agent that helps recruiters select "
        "SHL assessments based on their hiring needs."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for Swagger UI and external access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health endpoint
@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}


# Mount chat router
app.include_router(chat_router, tags=["Chat"])


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", settings.port))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
