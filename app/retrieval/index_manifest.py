import json
from pathlib import Path
from typing import Dict, Any, Optional
from app.config import Config


class IndexManifest:
    """Manages index metadata manifest to detect model drift or configuration corruption."""
    
    MANIFEST_FILE = Config.INDEX_DIR / "index_manifest.json"

    @classmethod
    def save_manifest(cls, vector_count: int, chunk_count: int) -> None:
        cls.MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
        manifest_data = {
            "embedding_model": Config.EMBEDDING_MODEL_NAME,
            "embedding_dim": Config.EMBEDDING_DIM,
            "chunk_size": Config.CHUNK_SIZE,
            "chunk_overlap": Config.CHUNK_OVERLAP,
            "vector_count": vector_count,
            "chunk_count": chunk_count,
            "index_type": "FAISS_IndexFlatIP + BM25Plus"
        }
        with open(cls.MANIFEST_FILE, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

    @classmethod
    def load_manifest(cls) -> Optional[Dict[str, Any]]:
        if not cls.MANIFEST_FILE.exists():
            return None
        try:
            with open(cls.MANIFEST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    @classmethod
    def validate_integrity(cls) -> Dict[str, Any]:
        """Validate if the persisted index matches current system configuration."""
        manifest = cls.load_manifest()
        if not manifest:
            return {"status": "uninitialized", "valid": True, "message": "No manifest generated yet."}

        if manifest.get("embedding_model") != Config.EMBEDDING_MODEL_NAME:
            return {
                "status": "stale",
                "valid": False,
                "message": f"Embedding model changed from {manifest.get('embedding_model')} to {Config.EMBEDDING_MODEL_NAME}. Rebuild required."
            }
        
        if manifest.get("embedding_dim") != Config.EMBEDDING_DIM:
            return {
                "status": "corrupt",
                "valid": False,
                "message": f"Embedding dimension mismatch ({manifest.get('embedding_dim')} vs {Config.EMBEDDING_DIM}). Rebuild required."
            }

        return {"status": "current", "valid": True, "message": "Index manifest is synchronized."}
