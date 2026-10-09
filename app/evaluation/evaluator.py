import json
import re
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List
from app.config import Config
from app.database import get_db_cursor
from app.generation.rag_pipeline import RAGPipeline

DATASET_PATH = Path(__file__).resolve().parent / "dataset.json"


class Evaluator:
    """
    Academic Evaluation Framework.
    Conducts comparative ablation benchmarks across:
    1. Baseline: Dense Retrieval only -> LLM
    2. System B: Dense Retrieval -> CrossEncoder Reranking -> LLM
    3. System C: Hybrid Retrieval (Dense + BM25) -> CrossEncoder Reranking -> LLM
    4. Final System: Query Rewriting + Hybrid Retrieval + Reranking + Evidence Filtering + Faithfulness Verification
    """

    def __init__(self):
        self.pipeline = RAGPipeline()

    def run_benchmark(self) -> Dict[str, Any]:
        with open(DATASET_PATH, "r", encoding="utf-8") as f:
            test_cases = json.load(f)

        configs = [
            {
                "name": "Baseline (Dense)",
                "enable_dense": True,
                "enable_bm25": False,
                "enable_rerank": False,
                "enable_rewriting": False
            },
            {
                "name": "System B (Dense + Rerank)",
                "enable_dense": True,
                "enable_bm25": False,
                "enable_rerank": True,
                "enable_rewriting": False
            },
            {
                "name": "System C (Hybrid + Rerank)",
                "enable_dense": True,
                "enable_bm25": True,
                "enable_rerank": True,
                "enable_rewriting": False
            },
            {
                "name": "Final System (Full RAG Pipeline)",
                "enable_dense": True,
                "enable_bm25": True,
                "enable_rerank": True,
                "enable_rewriting": True
            }
        ]

        benchmark_results = []

        for cfg in configs:
            hits = 0
            reciprocal_ranks = []
            faithfulness_scores = []
            answer_relevances = []
            latencies = []

            for tc in test_cases:
                q = tc["question"]
                keywords = tc.get("expected_keywords", [])
                should_abstain = tc.get("should_abstain", False)
                conv_history = tc.get("conversation_history", [])

                t0 = time.time()
                # If conversational turn, synthesize temporary dialogue context
                if conv_history and cfg["enable_rewriting"]:
                    last_user = conv_history[-1]["content"] if conv_history else ""
                    rewritten_q = self.pipeline.rewriter.rewrite(q, conv_history)
                else:
                    rewritten_q = q

                res = self.pipeline.process_query(
                    question=rewritten_q,
                    enable_dense=cfg["enable_dense"],
                    enable_bm25=cfg["enable_bm25"],
                    enable_rerank=cfg["enable_rerank"],
                    enable_rewriting=False # already handled if conversation turn
                )
                lat = time.time() - t0
                latencies.append(lat)
                faithfulness_scores.append(res.get("faithfulness_score", 0.0))

                # Retrieval evaluation
                citations = res.get("citations", [])
                if should_abstain:
                    # If query should abstain, successful if evidence_status is INSUFFICIENT
                    if res.get("evidence_status") == "INSUFFICIENT EVIDENCE":
                        hits += 1
                        reciprocal_ranks.append(1.0)
                    else:
                        reciprocal_ranks.append(0.0)
                else:
                    found_rank = 0
                    for rank, c in enumerate(citations, start=1):
                        txt_lower = c["text"].lower()
                        if any(kw in txt_lower for kw in keywords):
                            found_rank = rank
                            break
                    if found_rank > 0:
                        hits += 1
                        reciprocal_ranks.append(1.0 / found_rank)
                    else:
                        reciprocal_ranks.append(0.0)

                # Answer relevance: token overlap between generated answer and ground-truth expected answer
                expected_ans = tc.get("expected_answer", "")
                gen_ans = res.get("answer", "")
                if should_abstain:
                    ans_rel = 1.0 if res.get("evidence_status") == "INSUFFICIENT EVIDENCE" else 0.0
                elif expected_ans and gen_ans:
                    exp_tokens = set(re.findall(r'\b[a-zA-Z]{3,}\b', expected_ans.lower()))
                    gen_tokens = set(re.findall(r'\b[a-zA-Z]{3,}\b', gen_ans.lower()))
                    ans_rel = len(exp_tokens.intersection(gen_tokens)) / len(exp_tokens) if exp_tokens else 1.0
                else:
                    ans_rel = 0.5
                answer_relevances.append(ans_rel)

            n = len(test_cases)
            hit_rate = round(hits / n, 3) if n else 0.0
            mrr = round(sum(reciprocal_ranks) / n, 3) if n else 0.0
            mean_faithfulness = round(sum(faithfulness_scores) / n, 3) if n else 0.0
            mean_ans_rel = round(sum(answer_relevances) / n, 3) if n else 0.0
            mean_latency = round(sum(latencies) / n, 4) if n else 0.0

            result_entry = {
                "id": str(uuid.uuid4()),
                "pipeline_name": cfg["name"],
                "num_samples": n,
                "hit_rate": hit_rate,
                "mrr": mrr,
                "faithfulness": mean_faithfulness,
                "answer_relevance": mean_ans_rel,
                "latency_sec": mean_latency
            }
            benchmark_results.append(result_entry)

            # Persist to database
            with get_db_cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO evaluations (
                        id, pipeline_name, num_samples, mean_hit_rate, mean_mrr,
                        mean_faithfulness, mean_answer_relevance, mean_latency, detailed_results
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        result_entry["id"],
                        result_entry["pipeline_name"],
                        result_entry["num_samples"],
                        result_entry["hit_rate"],
                        result_entry["mrr"],
                        result_entry["faithfulness"],
                        result_entry["answer_relevance"],
                        result_entry["latency_sec"],
                        json.dumps(result_entry)
                    )
                )

        # Compute insights dynamically from empirical measurements
        b_map = {b["pipeline_name"]: b for b in benchmark_results}
        baseline = b_map.get("Baseline (Dense)", {})
        sys_b = b_map.get("System B (Dense + Rerank)", {})
        sys_c = b_map.get("System C (Hybrid + Rerank)", {})
        final_sys = b_map.get("Final System (Full RAG Pipeline)", {})

        mrr_gain = sys_b.get("mrr", 0) - baseline.get("mrr", 0)
        hybrid_hit_diff = sys_c.get("hit_rate", 0) - baseline.get("hit_rate", 0)
        lat_diff = final_sys.get("latency_sec", 0) - baseline.get("latency_sec", 0)

        rq1_text = f"Hybrid retrieval achieved Hit Rate of {sys_c.get('hit_rate', 0):.2f} vs {baseline.get('hit_rate', 0):.2f} (delta: {hybrid_hit_diff:+.2f}) on keyword/dense test queries."
        rq2_text = f"CrossEncoder reranking changed MRR from {baseline.get('mrr', 0):.3f} to {sys_b.get('mrr', 0):.3f} (delta: {mrr_gain:+.3f}) by re-scoring token cross-attentions."
        rq3_text = f"Conversational query rewriting sustained Hit Rate of {final_sys.get('hit_rate', 0):.2f} and MRR of {final_sys.get('mrr', 0):.3f} across multi-turn follow-up queries."
        rq4_text = f"Post-generation verification achieved mean faithfulness of {final_sys.get('faithfulness', 0):.2f} on evidence-grounded claims."
        rq5_text = f"Empirical compute budget: Baseline latency was {baseline.get('latency_sec', 0):.4f}s vs Full System latency of {final_sys.get('latency_sec', 0):.4f}s (delta: {lat_diff:+.4f}s)."

        return {
            "benchmarks": benchmark_results,
            "research_insights": {
                "RQ1_hybrid_vs_dense": rq1_text,
                "RQ2_reranker_impact": rq2_text,
                "RQ3_rewriting_impact": rq3_text,
                "RQ4_verification": rq4_text,
                "RQ5_latency_tradeoff": rq5_text
            }
        }
