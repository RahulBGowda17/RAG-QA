from typing import List, Dict, Any, Optional
from app.config import Config
from app.database import get_db_cursor
from app.embeddings.embedding_service import EmbeddingService
from app.retrieval.vector_store import FAISSVectorStore
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.reranker import RerankerService


def fetch_chunk_metadata_bulk(chunk_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Retrieve chunk and document metadata from SQLite for a list of chunk IDs."""
    if not chunk_ids:
        return {}

    placeholders = ",".join(["?"] * len(chunk_ids))
    sql = f"""
        SELECT 
            c.id AS chunk_id,
            c.document_id,
            c.chunk_index,
            c.page_number,
            c.section,
            c.text,
            c.token_count,
            d.filename,
            d.file_type
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE c.id IN ({placeholders})
    """
    with get_db_cursor() as cursor:
        cursor.execute(sql, chunk_ids)
        rows = cursor.fetchall()

    return {row["chunk_id"]: dict(row) for row in rows}


class HybridRetriever:
    """Coordinates Dense (FAISS) + Sparse (BM25) search with Reciprocal Rank Fusion & Reranking."""

    def __init__(self):
        self.embedding_service = EmbeddingService.get_instance()
        self.vector_store = FAISSVectorStore.get_instance()
        self.bm25_retriever = BM25Retriever.get_instance()
        self.reranker = RerankerService.get_instance()

    def sync_bm25_with_db(self) -> None:
        """Re-index BM25 in memory with all indexed chunks from SQLite."""
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id, text FROM chunks ORDER BY created_at ASC")
            rows = cursor.fetchall()
            chunks = [{"id": r["id"], "text": r["text"]} for r in rows]
            self.bm25_retriever.index_chunks(chunks)

    def retrieve(
        self,
        query: str,
        document_ids: Optional[List[str]] = None,
        dense_top_k: Optional[int] = None,
        bm25_top_k: Optional[int] = None,
        candidate_pool_size: Optional[int] = None,
        rerank_top_k: Optional[int] = None,
        enable_dense: bool = True,
        enable_bm25: bool = True,
        enable_rerank: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Execute Hybrid Retrieval Pipeline:
        1. Query -> FAISS (Dense)
        2. Query -> BM25 (Sparse)
        3. Reciprocal Rank Fusion (RRF) -> Candidate Pool
        4. Cross-Encoder Reranking -> Top Evidence Chunks
        """
        dense_k = dense_top_k or Config.DENSE_TOP_K
        bm25_k = bm25_top_k or Config.BM25_TOP_K
        pool_size = candidate_pool_size or Config.CANDIDATE_POOL_SIZE
        rerank_k = rerank_top_k or Config.RERANK_TOP_K

        dense_results = []
        if enable_dense and self.vector_store.size() > 0:
            query_vector = self.embedding_service.embed_query(query)
            dense_results = self.vector_store.search(query_vector, top_k=dense_k)

        bm25_results = []
        if enable_bm25:
            bm25_results = self.bm25_retriever.search(query, top_k=bm25_k)

        # Reciprocal Rank Fusion (RRF constant c=60)
        rrf_scores: Dict[str, float] = {}
        rrf_meta: Dict[str, Dict[str, Any]] = {}

        for rank, res in enumerate(dense_results, start=1):
            cid = res["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (60.0 + rank))
            rrf_meta.setdefault(cid, {})["dense_score"] = res["score"]
            rrf_meta[cid]["dense_rank"] = rank

        for rank, res in enumerate(bm25_results, start=1):
            cid = res["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (60.0 + rank))
            rrf_meta.setdefault(cid, {})["bm25_score"] = res["score"]
            rrf_meta[cid]["bm25_rank"] = rank

        # Sort candidate pool by RRF score
        sorted_candidates = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:pool_size]
        if not sorted_candidates:
            return []

        candidate_ids = [c[0] for c in sorted_candidates]
        chunks_meta = fetch_chunk_metadata_bulk(candidate_ids)

        # Assemble candidate items
        candidates = []
        for cid, rrf_score in sorted_candidates:
            if cid in chunks_meta:
                item = dict(chunks_meta[cid])
                # If document_ids filter specified, filter out other documents
                if document_ids and item.get("document_id") not in document_ids:
                    continue
                item["rrf_score"] = rrf_score
                item["dense_score"] = rrf_meta[cid].get("dense_score", 0.0)
                item["bm25_score"] = rrf_meta[cid].get("bm25_score", 0.0)
                candidates.append(item)

        if not candidates:
            return []

        # Rerank candidate pool if enabled
        if enable_rerank:
            candidate_texts = [c["text"] for c in candidates]
            rerank_scores = self.reranker.rerank(query, candidate_texts)
            for c, score in zip(candidates, rerank_scores):
                c["rerank_score"] = score
            # Sort descending by rerank score
            candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
        else:
            for c in candidates:
                c["rerank_score"] = c["rrf_score"]

        # Assign final rank
        final_results = candidates[:rerank_k]
        for idx, item in enumerate(final_results, start=1):
            item["rank"] = idx

        return final_results
