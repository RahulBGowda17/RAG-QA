import re
from typing import List, Dict, Any, Tuple


class FaithfulnessVerifier:
    """
    Evidence grounding and faithfulness verification service.
    Evaluates whether generated answer claims are supported by the retrieved context.
    """

    @staticmethod
    def calculate_evidence_status(
        rerank_scores: List[float],
        has_abstention: bool
    ) -> str:
        """
        Determine evidence strength category based on CrossEncoder rerank scores.
        Status: HIGH EVIDENCE, MEDIUM EVIDENCE, LOW EVIDENCE, INSUFFICIENT EVIDENCE
        """
        if has_abstention or not rerank_scores:
            return "INSUFFICIENT EVIDENCE"

        top_score = max(rerank_scores)
        if top_score > 2.0:
            return "HIGH EVIDENCE"
        elif top_score > -2.0:
            return "MEDIUM EVIDENCE"
        elif top_score > -8.0:
            return "LOW EVIDENCE"
        else:
            return "INSUFFICIENT EVIDENCE"

    def verify_answer(
        self,
        answer: str,
        evidence_chunks: List[Dict[str, Any]],
        rerank_scores: List[float]
    ) -> Tuple[str, str, float]:
        """
        Verify generated answer against evidence.
        Returns: (decision, evidence_status, faithfulness_score)
        Possible decisions: VERIFIED, PARTIALLY_SUPPORTED, UNSUPPORTED, INSUFFICIENT_EVIDENCE
        """
        if not answer or not answer.strip():
            return "UNSUPPORTED", "INSUFFICIENT EVIDENCE", 0.0

        ans_lower = answer.lower()
        
        # Check if model abstained
        abstention_cues = [
            "sufficient information was not found",
            "could not be found",
            "not found in the provided",
            "information is not available",
            "no relevant evidence"
        ]
        is_abstention = any(cue in ans_lower for cue in abstention_cues)
        if is_abstention:
            return "INSUFFICIENT_EVIDENCE", "INSUFFICIENT EVIDENCE", 1.0

        if not evidence_chunks:
            return "UNSUPPORTED", "INSUFFICIENT EVIDENCE", 0.0

        # Extract content words from answer and evidence
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "and", "or", "to", "in", "of",
            "for", "on", "with", "as", "by", "at", "from", "that", "this", "it", "be",
            "based", "retrieved", "evidence", "provided", "documents"
        }
        ans_tokens = set(re.findall(r'\b[a-zA-Z]{3,}\b', ans_lower)) - stop_words

        combined_evidence = " ".join([c.get("text", "") for c in evidence_chunks]).lower()
        ev_tokens = set(re.findall(r'\b[a-zA-Z]{3,}\b', combined_evidence)) - stop_words

        if not ans_tokens:
            return "PARTIALLY_SUPPORTED", "MEDIUM EVIDENCE", 0.5

        # Measure lexical overlap ratio
        supported_tokens = ans_tokens.intersection(ev_tokens)
        overlap_ratio = len(supported_tokens) / len(ans_tokens)

        evidence_status = self.calculate_evidence_status(rerank_scores, has_abstention=False)

        if overlap_ratio >= 0.65:
            decision = "VERIFIED"
        elif overlap_ratio >= 0.40:
            decision = "PARTIALLY_SUPPORTED"
        else:
            decision = "UNSUPPORTED"

        return decision, evidence_status, round(overlap_ratio, 3)
