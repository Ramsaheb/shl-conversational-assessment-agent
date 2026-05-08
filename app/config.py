"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings with environment variable loading."""

    # Groq API
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"

    # ChromaDB
    chroma_persist_dir: str = "./chroma_db"

    # Embedding Model
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Server
    port: int = 8000
    log_level: str = "INFO"

    # Retrieval
    max_retrieval_results: int = 20
    top_k_recommendations: int = 10

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
