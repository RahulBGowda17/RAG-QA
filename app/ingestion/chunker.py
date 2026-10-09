import re
import uuid
from typing import List, Dict, Any
from app.config import Config


def split_text_into_sentences(text: str) -> List[str]:
    """Split text into sentences using regex boundary matching."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def count_tokens(text: str) -> int:
    """Accurate token estimation based on whitespace and subword factor (1 word in English ~ 1.3 subword tokens)."""
    if not text or not text.strip():
        return 0
    words = text.strip().split()
    return max(1, round(len(words) * 1.3))


def chunk_document_elements(
    document_id: str,
    elements: List[Dict[str, Any]],
    chunk_size_tokens: int = None,
    chunk_overlap_tokens: int = None
) -> List[Dict[str, Any]]:
    """
    Intelligent structural token-aware chunker:
    - Respects paragraph and sentence boundaries.
    - Preserves metadata (document_id, page_number, section).
    - Budgets strictly in TOKENS (default 350-500 tokens, 50-100 overlap).
    """
    max_tokens = chunk_size_tokens if chunk_size_tokens is not None else getattr(Config, "CHUNK_SIZE", 400)
    overlap_tokens = chunk_overlap_tokens if chunk_overlap_tokens is not None else getattr(Config, "CHUNK_OVERLAP", 80)

    chunks = []
    chunk_index = 0

    for elem in elements:
        page_number = elem.get("page_number", 1)
        section = elem.get("section", "General")
        text = elem.get("text", "")
        
        if not text:
            continue

        elem_tokens = count_tokens(text)
        if elem_tokens <= max_tokens:
            chunks.append({
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "chunk_index": chunk_index,
                "page_number": page_number,
                "section": section,
                "text": text,
                "token_count": elem_tokens
            })
            chunk_index += 1
            continue

        # Sentence-based boundary chunking budgeted by tokens
        sentences = split_text_into_sentences(text)
        current_chunk_sentences = []
        current_token_count = 0

        for sent in sentences:
            sent_tokens = count_tokens(sent)
            if current_token_count + sent_tokens > max_tokens and current_chunk_sentences:
                # Flush chunk
                chunk_str = " ".join(current_chunk_sentences)
                chunks.append({
                    "id": str(uuid.uuid4()),
                    "document_id": document_id,
                    "chunk_index": chunk_index,
                    "page_number": page_number,
                    "section": section,
                    "text": chunk_str,
                    "token_count": current_token_count
                })
                chunk_index += 1

                # Token-based overlap logic
                overlap_acc = 0
                overlap_sentences = []
                for s in reversed(current_chunk_sentences):
                    s_tok = count_tokens(s)
                    if overlap_acc + s_tok <= overlap_tokens:
                        overlap_sentences.insert(0, s)
                        overlap_acc += s_tok
                    else:
                        break
                
                current_chunk_sentences = overlap_sentences
                current_token_count = sum(count_tokens(s) for s in current_chunk_sentences)

            current_chunk_sentences.append(sent)
            current_token_count += sent_tokens

        # Flush final remaining sentence chunk
        if current_chunk_sentences:
            chunk_str = " ".join(current_chunk_sentences)
            chunks.append({
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "chunk_index": chunk_index,
                "page_number": page_number,
                "section": section,
                "text": chunk_str,
                "token_count": current_token_count
            })
            chunk_index += 1

    return chunks
