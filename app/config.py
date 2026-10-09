import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory of Project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env
load_dotenv(BASE_DIR / ".env")


class Config:
    """Central configuration class for RAG-QA system."""
    
    # Environment & Server
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")
    PORT = int(os.getenv("PORT", "5000"))
    HOST = os.getenv("HOST", "127.0.0.1")
    SECRET_KEY = os.getenv("SECRET_KEY", "rag-qa-super-secret-academic-dev-key")

    # Storage Paths
    DATA_DIR = BASE_DIR / os.getenv("DATA_DIR", "data")
    UPLOAD_DIR = BASE_DIR / os.getenv("UPLOAD_DIR", "data/uploads")
    INDEX_DIR = BASE_DIR / os.getenv("INDEX_DIR", "data/indices")
    DATABASE_PATH = BASE_DIR / os.getenv("DATABASE_PATH", "data/rag_qa.db")
    FAISS_INDEX_PATH = BASE_DIR / os.getenv("FAISS_INDEX_PATH", "data/indices/faiss_index.bin")

    # Ingestion & Upload Security
    MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "16"))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
    ALLOWED_MIME_TYPES = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain"
    }

    # Chunking Hyperparameters
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))

    # Embeddings & Vector Store
    EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
    EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))
    NORMALIZE_EMBEDDINGS = True

    # Retrieval & Reranker
    DENSE_TOP_K = int(os.getenv("DENSE_TOP_K", "10"))
    BM25_TOP_K = int(os.getenv("BM25_TOP_K", "10"))
    CANDIDATE_POOL_SIZE = int(os.getenv("CANDIDATE_POOL_SIZE", "15"))
    RERANKER_MODEL_NAME = os.getenv("RERANKER_MODEL_NAME", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "4"))
    EVIDENCE_THRESHOLD = float(os.getenv("EVIDENCE_THRESHOLD", "0.05"))

    # LLM Provider
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "local_mock")
    LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "phi3:mini")
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    LLM_API_KEY = os.getenv("LLM_API_KEY", "none")
    MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "2000"))
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))

    @classmethod
    def ensure_directories(cls):
        """Ensure all runtime directories exist."""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        cls.INDEX_DIR.mkdir(parents=True, exist_ok=True)
