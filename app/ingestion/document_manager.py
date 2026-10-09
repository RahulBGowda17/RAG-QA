import uuid
from pathlib import Path
from typing import Dict, Any, List
from app.config import Config
from app.database import get_db_cursor
from app.ingestion import validate_upload, compute_file_hash, parse_document, chunk_document_elements
from app.embeddings.embedding_service import EmbeddingService
from app.retrieval.vector_store import FAISSVectorStore
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.index_manifest import IndexManifest


class DocumentManager:
    """Coordinates document ingestion, chunking, vector indexing, and deletion/rebuilding."""

    @staticmethod
    def ingest_document(filename: str, file_bytes: bytes) -> Dict[str, Any]:
        """Validate, store, parse, chunk, embed, and index a document."""
        clean_filename, file_type, file_size = validate_upload(filename, file_bytes)
        file_hash = compute_file_hash(file_bytes)

        # Check for duplicate
        with get_db_cursor() as cur:
            cur.execute("SELECT id, filename FROM documents WHERE file_hash = ?", (file_hash,))
            existing = cur.fetchone()
            if existing:
                raise ValueError(f"Document already exists with filename '{existing['filename']}' (matching SHA-256 hash).")

        doc_id = str(uuid.uuid4())
        save_path = Config.UPLOAD_DIR / f"{doc_id}_{clean_filename}"
        with open(save_path, "wb") as f:
            f.write(file_bytes)

        try:
            # Parse document
            elements, page_count = parse_document(file_type, file_bytes)
            # Chunk elements
            chunks = chunk_document_elements(doc_id, elements)
            
            if not chunks:
                raise ValueError("No text content could be extracted from the document.")

            # Insert document into SQLite
            with get_db_cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO documents (id, filename, file_hash, file_type, file_size, page_count, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'indexing')
                    """,
                    (doc_id, clean_filename, file_hash, file_type, file_size, page_count)
                )

                for c in chunks:
                    cur.execute(
                        """
                        INSERT INTO chunks (id, document_id, chunk_index, page_number, section, text, token_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (c["id"], doc_id, c["chunk_index"], c["page_number"], c["section"], c["text"], c["token_count"])
                    )

            # Generate embeddings and add to FAISS
            emb_svc = EmbeddingService.get_instance()
            chunk_texts = [c["text"] for c in chunks]
            chunk_ids = [c["id"] for c in chunks]
            vectors = emb_svc.embed_texts(chunk_texts)

            vector_store = FAISSVectorStore.get_instance()
            vector_store.add_vectors(chunk_ids, vectors)

            # Sync BM25
            with get_db_cursor() as cur:
                cur.execute("UPDATE documents SET status = 'indexed' WHERE id = ?", (doc_id,))
                cur.execute("SELECT id, text FROM chunks")
                all_chunks = [{"id": r["id"], "text": r["text"]} for r in cur.fetchall()]
                BM25Retriever.get_instance().index_chunks(all_chunks)

            # Record index manifest
            IndexManifest.save_manifest(
                vector_count=vector_store.size(),
                chunk_count=len(all_chunks)
            )

            return {
                "id": doc_id,
                "filename": clean_filename,
                "file_type": file_type,
                "file_size": file_size,
                "page_count": page_count,
                "chunk_count": len(chunks),
                "status": "indexed"
            }

        except Exception as e:
            with get_db_cursor() as cur:
                cur.execute("UPDATE documents SET status = 'error', error_message = ? WHERE id = ?", (str(e), doc_id))
            raise

    @staticmethod
    def delete_document(doc_id: str) -> None:
        """Delete a document and rebuild the FAISS vector index and BM25 index."""
        with get_db_cursor() as cur:
            cur.execute("SELECT filename FROM documents WHERE id = ?", (doc_id,))
            doc = cur.fetchone()
            if not doc:
                raise ValueError("Document not found.")

            # Delete file on disk if exists
            pattern = f"{doc_id}_*"
            for p in Config.UPLOAD_DIR.glob(pattern):
                try:
                    p.unlink()
                except Exception:
                    pass

            # Cascades delete to chunks and retrieval_results
            cur.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

        # Rebuild FAISS and BM25 from remaining chunks
        DocumentManager.rebuild_indices()

    @staticmethod
    def reindex_document(doc_id: str) -> Dict[str, Any]:
        """Re-parse and re-index a specific document."""
        with get_db_cursor() as cur:
            cur.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
            doc = cur.fetchone()
            if not doc:
                raise ValueError("Document not found.")

            # Find document file
            pattern = f"{doc_id}_*"
            files = list(Config.UPLOAD_DIR.glob(pattern))
            if not files:
                raise ValueError("Original file not found on disk.")
            
            with open(files[0], "rb") as f:
                file_bytes = f.read()

            elements, page_count = parse_document(doc["file_type"], file_bytes)
            chunks = chunk_document_elements(doc_id, elements)

            # Clear old chunks for this document
            cur.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))
            for c in chunks:
                cur.execute(
                    """
                    INSERT INTO chunks (id, document_id, chunk_index, page_number, section, text, token_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (c["id"], doc_id, c["chunk_index"], c["page_number"], c["section"], c["text"], c["token_count"])
                )

        # Rebuild indices
        DocumentManager.rebuild_indices()
        return {"id": doc_id, "chunk_count": len(chunks), "status": "indexed"}

    @staticmethod
    def rebuild_indices() -> None:
        """Rebuild entire FAISS index and BM25 index from active database chunks."""
        with get_db_cursor() as cur:
            cur.execute("SELECT id, text FROM chunks ORDER BY created_at ASC")
            all_chunks = [dict(r) for r in cur.fetchall()]

        vector_store = FAISSVectorStore.get_instance()
        vector_store.reset()

        if all_chunks:
            chunk_ids = [c["id"] for c in all_chunks]
            chunk_texts = [c["text"] for c in all_chunks]
            emb_svc = EmbeddingService.get_instance()
            vectors = emb_svc.embed_texts(chunk_texts)
            vector_store.add_vectors(chunk_ids, vectors)

        BM25Retriever.get_instance().index_chunks(all_chunks)
        IndexManifest.save_manifest(
            vector_count=vector_store.size(),
            chunk_count=len(all_chunks)
        )
