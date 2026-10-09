import re
import threading
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Plus


def tokenize(text: str) -> List[str]:
    """Simple lowercase alphanumeric tokenization."""
    return re.findall(r'\b\w+\b', text.lower())


class BM25Retriever:
    """Thread-safe BM25 keyword retrieval engine using BM25Plus."""
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.chunk_ids: List[str] = []
        self.corpus_tokens: List[List[str]] = []
        self.bm25: Optional[BM25Plus] = None
        self.rw_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "BM25Retriever":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def index_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        """
        Build BM25 index from a list of chunk dicts:
        [{'id': str, 'text': str}, ...]
        """
        with self.rw_lock:
            self.chunk_ids = [c["id"] for c in chunks]
            self.corpus_tokens = [tokenize(c["text"]) for c in chunks]
            if self.corpus_tokens:
                self.bm25 = BM25Plus(self.corpus_tokens)
            else:
                self.bm25 = None

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Search top_k candidates matching query keywords.
        Returns: list of {"chunk_id": str, "score": float}
        """
        with self.rw_lock:
            if not self.bm25 or not self.chunk_ids:
                return []

            query_tokens = tokenize(query)
            if not query_tokens:
                return []

            scores = self.bm25.get_scores(query_tokens)
            # Pair chunk_id with score
            scored_pairs = [(self.chunk_ids[i], float(scores[i])) for i in range(len(self.chunk_ids))]
            # Sort descending by score
            scored_pairs.sort(key=lambda x: x[1], reverse=True)

            results = []
            for chunk_id, score in scored_pairs[:top_k]:
                if score > 0:
                    results.append({"chunk_id": chunk_id, "score": score})
            return results
