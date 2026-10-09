import re
from typing import List, Dict, Any


PRONOUNS_AND_REFERENCES = {
    "it", "its", "they", "them", "their", "this", "these", "that", "those",
    "such", "the same", "he", "she", "his", "her"
}


class QueryRewriter:
    """
    Conversation-aware query rewriting service.
    Resolves anaphora and ambiguous follow-ups into standalone retrieval queries.
    """

    def rewrite(self, current_question: str, history: List[Dict[str, str]]) -> str:
        """
        Rewrite follow-up questions to incorporate coreferences from recent turns.
        Falls back safely to current_question if standalone or rewriting is not required.
        """
        if not current_question or not current_question.strip():
            return current_question

        clean_q = current_question.strip()
        tokens = re.findall(r'\b\w+\b', clean_q.lower())

        # If no conversation history exists, return original
        if not history:
            return clean_q

        # Check if question contains demonstrative pronouns or follow-up indicators
        has_reference = any(tok in PRONOUNS_AND_REFERENCES for tok in tokens)
        is_short_followup = len(tokens) <= 6

        if not (has_reference or is_short_followup):
            return clean_q

        # Extract recent user queries or topic nouns from the last user turn
        last_user_turn = None
        for turn in reversed(history):
            if turn.get("role") == "user":
                last_user_turn = turn.get("content", "")
                break

        if not last_user_turn:
            return clean_q

        # Extract dominant topic from the last user question
        # e.g., "What is RAG?" -> "RAG"
        topic_match = re.search(r'(?:what is|what are|explain|define|tell me about)\s+([^?.,]+)', last_user_turn, re.IGNORECASE)
        topic = topic_match.group(1).strip() if topic_match else last_user_turn.strip()

        # If current question is e.g. "What are its advantages?" -> "What are advantages of <topic>?"
        rewritten = clean_q
        for pronoun in ["its", "their", "this", "these", "it"]:
            pattern = re.compile(rf'\b{pronoun}\b', re.IGNORECASE)
            if pattern.search(rewritten):
                rewritten = pattern.sub(f"the {topic}", rewritten)
                break

        if rewritten.lower() == clean_q.lower() and is_short_followup:
            rewritten = f"{clean_q} regarding {topic}"

        return rewritten.strip()
