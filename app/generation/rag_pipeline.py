import time
import uuid
from typing import List, Dict, Any, Optional
from app.config import Config
from app.database import get_db_cursor
from app.retrieval.hybrid_retriever import HybridRetriever
from app.generation.query_rewriter import QueryRewriter
from app.generation.prompt_builder import construct_chat_messages
from app.generation.llm_provider import get_llm_provider
from app.generation.verifier import FaithfulnessVerifier


class RAGPipeline:
    """
    End-to-End Orchestrator for RAG-QA:
    Question -> Rewriter -> Hybrid Retrieval -> Reranker -> Evidence Filter -> Grounded LLM -> Verifier -> Citations & Persistence.
    """

    def __init__(self):
        self.retriever = HybridRetriever()
        self.rewriter = QueryRewriter()
        self.llm = get_llm_provider()
        self.verifier = FaithfulnessVerifier()

    def process_query(
        self,
        question: str,
        conversation_id: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
        enable_rewriting: bool = True,
        enable_bm25: bool = True,
        enable_dense: bool = True,
        enable_rerank: bool = True
    ) -> Dict[str, Any]:
        start_time = time.time()
        
        # 1. Fetch recent conversation history (latest 6 messages in chronological order)
        history = []
        if conversation_id:
            with get_db_cursor() as cur:
                cur.execute(
                    """
                    SELECT role, content FROM (
                        SELECT role, content, created_at 
                        FROM messages 
                        WHERE conversation_id = ? 
                        ORDER BY created_at DESC 
                        LIMIT 6
                    ) ORDER BY created_at ASC
                    """,
                    (conversation_id,)
                )
                rows = cur.fetchall()
                history = [{"role": r["role"], "content": r["content"]} for r in rows]

        # 2. Conversation-Aware Query Rewriting
        rewritten_question = question
        if enable_rewriting and history:
            rewritten_question = self.rewriter.rewrite(question, history)

        # 3. Hybrid Retrieval & Reranking
        retrieval_start = time.time()
        candidates = self.retriever.retrieve(
            query=rewritten_question,
            document_ids=document_ids,
            enable_dense=enable_dense,
            enable_bm25=enable_bm25,
            enable_rerank=enable_rerank
        )
        retrieval_latency = round(time.time() - retrieval_start, 4)

        # 4. Evidence Filtering (apply threshold)
        filtered_evidence = []
        rerank_scores = [c.get("rerank_score", 0.0) for c in candidates]
        
        # In CrossEncoder ms-marco, positive scores indicate relevant passages. Scores below -2.0 indicate irrelevance.
        # If top candidate score is below -2.0, no relevant evidence exists in corpus.
        has_sufficient_evidence = bool(rerank_scores and max(rerank_scores) > -2.0)
        
        if has_sufficient_evidence:
            for c in candidates:
                score = c.get("rerank_score", 0.0)
                if score >= Config.EVIDENCE_THRESHOLD or (len(filtered_evidence) == 0 and score > -2.0):
                    filtered_evidence.append(c)

        # 5. Grounded Generation
        generation_start = time.time()
        if not filtered_evidence:
            answer = "Based on the provided documents, sufficient information was not found to answer this question."
            decision = "INSUFFICIENT_EVIDENCE"
            evidence_status = "INSUFFICIENT EVIDENCE"
            faithfulness_score = 1.0
            citations = []
        else:
            messages = construct_chat_messages(
                question=rewritten_question,
                evidence_chunks=filtered_evidence,
                conversation_history=history
            )
            raw_answer = self.llm.generate(messages, temperature=Config.TEMPERATURE)
            
            # 6. Faithfulness & Evidence Verification
            decision, evidence_status, faithfulness_score = self.verifier.verify_answer(
                answer=raw_answer,
                evidence_chunks=filtered_evidence,
                rerank_scores=rerank_scores
            )
            
            # If verification discovers answer is unsupported, format notice
            if decision == "UNSUPPORTED":
                answer = (
                    "Based on the provided documents, sufficient verifiable evidence was not found "
                    "to substantiate this answer without unverified extrapolation."
                )
                evidence_status = "INSUFFICIENT EVIDENCE"
            else:
                answer = raw_answer

            # Format source citations
            citations = []
            for c in filtered_evidence:
                citations.append({
                    "chunk_id": c["chunk_id"],
                    "document_id": c["document_id"],
                    "filename": c["filename"],
                    "page_number": c["page_number"],
                    "section": c["section"],
                    "text": c["text"],
                    "rerank_score": round(c.get("rerank_score", 0.0), 4),
                    "rank": c.get("rank", 1)
                })

        generation_latency = round(time.time() - generation_start, 4)
        total_latency = round(time.time() - start_time, 4)

        # 7. Persist query & messages into SQLite
        query_id = str(uuid.uuid4())
        with get_db_cursor() as cur:
            cur.execute(
                """
                INSERT INTO queries (
                    id, conversation_id, original_question, rewritten_question,
                    answer, evidence_status, retrieval_latency, generation_latency, total_latency
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    query_id, conversation_id, question, rewritten_question,
                    answer, evidence_status, retrieval_latency, generation_latency, total_latency
                )
            )

            # Store retrieval results mapping
            for c in filtered_evidence:
                cur.execute(
                    """
                    INSERT INTO retrieval_results (
                        id, query_id, chunk_id, retrieval_method, initial_score, rerank_score, rank
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()), query_id, c["chunk_id"], "hybrid",
                        c.get("rrf_score", 0.0), c.get("rerank_score", 0.0), c.get("rank", 1)
                    )
                )

            # Append messages to conversation if conversation_id provided
            if conversation_id:
                cur.execute(
                    "INSERT INTO messages (id, conversation_id, role, content) VALUES (?, ?, ?, ?)",
                    (str(uuid.uuid4()), conversation_id, "user", question)
                )
                cur.execute(
                    "INSERT INTO messages (id, conversation_id, role, content) VALUES (?, ?, ?, ?)",
                    (str(uuid.uuid4()), conversation_id, "assistant", answer)
                )

        return {
            "query_id": query_id,
            "original_question": question,
            "rewritten_question": rewritten_question,
            "answer": answer,
            "evidence_status": evidence_status,
            "verification_decision": decision,
            "faithfulness_score": faithfulness_score,
            "citations": citations,
            "llm_provider": self.llm.__class__.__name__,
            "metrics": {
                "retrieval_latency": retrieval_latency,
                "generation_latency": generation_latency,
                "total_latency": total_latency
            }
        }
