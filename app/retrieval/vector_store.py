import json
import threading
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
import faiss
from app.config import Config


class FAISSVectorStore:
    """Thread-safe persistent FAISS vector store with chunk ID mapping."""
    _instance = None
    _lock = threading.Lock()

    def __init__(self, index_path: Optional[Path] = None):
        self.index_path = index_path or Config.FAISS_INDEX_PATH
        self.id_map_path = self.index_path.with_suffix(".map.json")
        self.dimension = Config.EMBEDDING_DIM
        self.rw_lock = threading.Lock()
        
        # In-memory structures
        self.index: faiss.IndexFlatIP = faiss.IndexFlatIP(self.dimension)
        self.chunk_ids: List[str] = []  # position i -> chunk_id
        
        self.load()

    @classmethod
    def get_instance(cls) -> "FAISSVectorStore":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def add_vectors(self, chunk_ids: List[str], vectors: np.ndarray) -> None:
        """Add normalized vectors and their corresponding chunk IDs to the index."""
        if len(chunk_ids) == 0:
            return
        
        if len(chunk_ids) != vectors.shape[0]:
            raise ValueError("Length of chunk_ids does not match number of vector rows.")
        
        with self.rw_lock:
            # Ensure float32 format
            vectors = vectors.astype(np.float32)
            self.index.add(vectors)
            self.chunk_ids.extend(chunk_ids)
            self.save()

    def search(self, query_vector: np.ndarray, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Search top_k most similar vectors.
        Returns: list of {"chunk_id": str, "score": float}
        """
        with self.rw_lock:
            total_elements = self.index.ntotal
            if total_elements == 0:
                return []
            
            k = min(top_k, total_elements)
            if query_vector.ndim == 1:
                query_vector = np.expand_dims(query_vector, axis=0)
            
            query_vector = query_vector.astype(np.float32)
            scores, indices = self.index.search(query_vector, k)
            
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0 or idx >= len(self.chunk_ids):
                    continue
                results.append({
                    "chunk_id": self.chunk_ids[idx],
                    "score": float(score)
                })
            return results

    def save(self) -> None:
        """Persist index and chunk ID map to disk."""
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.index_path))
        with open(self.id_map_path, "w", encoding="utf-8") as f:
            json.dump({"chunk_ids": self.chunk_ids}, f, indent=2)

    def load(self) -> None:
        """Load index and chunk ID map from disk if present."""
        if self.index_path.exists() and self.id_map_path.exists():
            try:
                self.index = faiss.read_index(str(self.index_path))
                with open(self.id_map_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.chunk_ids = data.get("chunk_ids", [])
            except Exception as e:
                # Reset if corrupted
                self.reset()
        else:
            self.reset()

    def reset(self) -> None:
        """Clear the vector index and map."""
        with self.rw_lock:
            self.index = faiss.IndexFlatIP(self.dimension)
            self.chunk_ids = []
            if self.index_path.exists():
                self.index_path.unlink()
            if self.id_map_path.exists():
                self.id_map_path.unlink()

    def size(self) -> int:
        return self.index.ntotal
