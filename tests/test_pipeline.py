import re
import pytest
from app.generation.query_rewriter import QueryRewriter
from app.generation.verifier import FaithfulnessVerifier


def test_query_rewriting_pronoun_resolution():
    rewriter = QueryRewriter()
    history = [
        {"role": "user", "content": "What is Retrieval-Augmented Generation?"},
        {"role": "assistant", "content": "RAG is an AI framework that connects LLMs to external data."}
    ]
    rewritten = rewriter.rewrite("What are its primary benefits?", history)
    assert "Retrieval-Augmented Generation" in rewritten or "RAG" in rewritten
    # Verify standalone pronoun 'its' was replaced
    assert not re.search(r'\bits\b', rewritten, re.IGNORECASE)


def test_faithfulness_verifier_abstention():
    verifier = FaithfulnessVerifier()
    answer = "Based on the provided documents, sufficient information was not found."
    decision, status, score = verifier.verify_answer(answer, [], [])
    assert decision == "INSUFFICIENT_EVIDENCE"
    assert status == "INSUFFICIENT EVIDENCE"


def test_faithfulness_verifier_grounded_answer():
    verifier = FaithfulnessVerifier()
    evidence = [
        {"text": "Transformers utilize self-attention mechanisms to weigh input tokens dynamically."}
    ]
    answer = "Transformers utilize self-attention mechanisms to weigh tokens."
    decision, status, score = verifier.verify_answer(answer, evidence, [4.5])
    assert decision in ("VERIFIED", "PARTIALLY_SUPPORTED")
    assert status == "HIGH EVIDENCE"
