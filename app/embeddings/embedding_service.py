import threading
from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
from app.config import Config


class EmbeddingService:
    """Thread-safe singleton service for computing sentence embeddings."""
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self.model_name = Config.EMBEDDING_MODEL_NAME
        # Load model once
        self.model = SentenceTransformer(self.model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        self._initialized = True

    @classmethod
    def get_instance(cls) -> "EmbeddingService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def embed_texts(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        Embed a list of texts into normalized float32 vectors.
        """
        if not texts:
            return np.empty((0, self.embedding_dim), dtype=np.float32)
        
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=Config.NORMALIZE_EMBEDDINGS,
            convert_to_numpy=True
        )
        return embeddings.astype(np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query into a 1D or (1, dim) vector."""
        if not query or not query.strip():
            raise ValueError("Query string cannot be empty.")
        
        emb = self.model.encode(
            query.strip(),
            show_progress_bar=False,
            normalize_embeddings=Config.NORMALIZE_EMBEDDINGS,
            convert_to_numpy=True
        )
        return emb.astype(np.float32)
