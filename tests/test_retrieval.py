import pytest
from app.embeddings.embedding_service import EmbeddingService
from app.retrieval.vector_store import FAISSVectorStore
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.reranker import RerankerService


def test_embedding_dimensions():
    emb = EmbeddingService.get_instance()
    vectors = emb.embed_texts(["First test document", "Second test document"])
    assert vectors.shape == (2, emb.embedding_dim)
    assert vectors.dtype.name == "float32"


def test_bm25_keyword_matching():
    retriever = BM25Retriever.get_instance()
    chunks = [
        {"id": "c1", "text": "Deep learning architectures and neural networks."},
        {"id": "c2", "text": "Gardening tips for growing tomatoes and cucumbers."}
    ]
    retriever.index_chunks(chunks)
    res = retriever.search("neural networks", top_k=2)
    assert len(res) > 0
    assert res[0]["chunk_id"] == "c1"


def test_reranker_relevance_scoring():
    reranker = RerankerService.get_instance()
    query = "What is reinforcement learning?"
    passages = [
        "Reinforcement learning is an area of machine learning where agents learn by rewards.",
        "Photosynthesis converts light into organic compounds."
    ]
    scores = reranker.rerank(query, passages)
    assert len(scores) == 2
    # The relevant passage must have a higher score than the irrelevant passage
    assert scores[0] > scores[1]
