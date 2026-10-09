import logging
from flask import Blueprint, jsonify
from app.database import get_db_cursor
from app.embeddings.embedding_service import EmbeddingService
from app.retrieval.vector_store import FAISSVectorStore
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.reranker import RerankerService
from app.retrieval.index_manifest import IndexManifest
from app.generation.llm_provider import get_llm_provider
from app.config import Config

logger = logging.getLogger(__name__)

health_bp = Blueprint("health_bp", __name__)


def _check_database() -> dict:
    try:
        with get_db_cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM documents")
            doc_count = cur.fetchone()["cnt"]
            cur.execute("SELECT COUNT(*) AS cnt FROM chunks")
            chunk_count = cur.fetchone()["cnt"]
        return {"status": "ok", "document_count": doc_count, "chunk_count": chunk_count}
    except Exception as e:
        logger.warning("Health check — database error: %s", e)
        return {"status": "error", "detail": "Database unavailable."}


def _check_embedding_model() -> dict:
    try:
        svc = EmbeddingService.get_instance()
        # Smoke-test with a minimal string
        svc.embed_texts(["health check"])
        return {"status": "ok", "model": Config.EMBEDDING_MODEL_NAME}
    except Exception as e:
        logger.warning("Health check — embedding model error: %s", e)
        return {"status": "error", "detail": "Embedding model unavailable."}


def _check_reranker() -> dict:
    try:
        RerankerService.get_instance()
        return {"status": "ok", "model": Config.RERANKER_MODEL_NAME}
    except Exception as e:
        logger.warning("Health check — reranker error: %s", e)
        return {"status": "error", "detail": "Reranker unavailable."}


def _check_faiss() -> dict:
    try:
        vs = FAISSVectorStore.get_instance()
        return {"status": "ok", "vector_count": vs.size()}
    except Exception as e:
        logger.warning("Health check — FAISS error: %s", e)
        return {"status": "error", "detail": "FAISS index unavailable."}


def _check_bm25() -> dict:
    try:
        bm25 = BM25Retriever.get_instance()
        corpus_size = len(bm25.corpus_tokens) if bm25.corpus_tokens else 0
        return {"status": "ok", "corpus_size": corpus_size}
    except Exception as e:
        logger.warning("Health check — BM25 error: %s", e)
        return {"status": "error", "detail": "BM25 index unavailable."}


def _check_llm() -> dict:
    try:
        provider = get_llm_provider()
        mode = provider.__class__.__name__
        healthy = provider.health_check() if hasattr(provider, "health_check") else True
        return {
            "status": "ok" if healthy else "degraded",
            "mode": mode,
        }
    except Exception as e:
        logger.warning("Health check — LLM error: %s", e)
        return {"status": "error", "detail": "LLM provider unavailable."}


def _check_index_manifest() -> dict:
    try:
        manifest = IndexManifest.load_manifest()
        if not manifest:
            return {"status": "uninitialized"}
        ok = IndexManifest.validate_integrity()
        return {"status": "current" if ok else "stale", "manifest": manifest}
    except Exception as e:
        logger.warning("Health check — manifest error: %s", e)
        return {"status": "error", "detail": "Index manifest unreadable."}


@health_bp.route("/api/health", methods=["GET"])
def health():
    """System health check endpoint."""
    db = _check_database()
    embedding = _check_embedding_model()
    reranker = _check_reranker()
    faiss = _check_faiss()
    bm25 = _check_bm25()
    llm = _check_llm()
    manifest = _check_index_manifest()

    # Determine overall status
    critical = [db, faiss, bm25]
    if any(c["status"] == "error" for c in critical):
        overall = "unhealthy"
    elif any(
        c["status"] in ("error", "degraded")
        for c in [embedding, reranker, llm]
    ):
        overall = "degraded"
    else:
        overall = "healthy"

    return jsonify({
        "status": overall,
        "database": db,
        "embedding_model": embedding,
        "reranker": reranker,
        "faiss": faiss,
        "bm25": bm25,
        "llm": llm,
        "index_manifest": manifest,
    }), 200 if overall != "unhealthy" else 503
