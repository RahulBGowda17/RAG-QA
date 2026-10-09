import threading
from typing import List, Tuple
from sentence_transformers import CrossEncoder
from app.config import Config


class RerankerService:
    """Thread-safe CrossEncoder reranker service."""
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.model_name = Config.RERANKER_MODEL_NAME
        # Load cross-encoder once
        self.model = CrossEncoder(self.model_name)

    @classmethod
    def get_instance(cls) -> "RerankerService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def rerank(self, query: str, candidate_texts: List[str]) -> List[float]:
        """
        Compute cross-encoder relevance scores for (query, text) pairs.
        Returns a list of float scores corresponding to candidate_texts.
        """
        if not candidate_texts:
            return []

        pairs = [[query, text] for text in candidate_texts]
        scores = self.model.predict(pairs, show_progress_bar=False)
        return [float(s) for s in scores]
