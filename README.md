# RAG-QA: Intelligent Evidence-Grounded Multi-Document Question Answering System

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![Flask 3.0](https://img.shields.io/badge/Framework-Flask%203.0-lightgrey.svg)](https://flask.palletsprojects.com/)
[![FAISS](https://img.shields.io/badge/Vector%20Store-FAISS-green.svg)](https://github.com/facebookresearch/faiss)
[![CrossEncoder](https://img.shields.io/badge/Reranker-CrossEncoder-orange.svg)](https://www.sbert.net/)
[![Tests](https://img.shields.io/badge/Tests-20%20Passed-brightgreen.svg)]()

> **Final-Year AIML Academic Project**: An end-to-end, production-grade Retrieval-Augmented Generation (RAG) system engineered for multi-document evidence grounding, verifiable citation attribution, and hallucination reduction.

---

## 1. Problem Statement & Motivation

Traditional Large Language Models (LLMs) suffer from knowledge cutoffs, hallucinated answers, and a lack of verifiable source attribution. While naive RAG systems often perform character slicing and basic vector retrieval, they introduce severe limitations:
- **Lexical Keyword Misses**: Semantic embeddings can struggle with exact domain-specific terminology or part numbers.
- **Lost Structural Context**: Arbitrary character slicing splits sentences across chunk boundaries.
- **Untrusted Prompt Injection**: Embedding raw document text directly into system instructions exposes the LLM to injection attacks.
- **Unverified Generation**: Models may hallucinate claims when retrieved context is only tangentially related.
- **Fake AI Silence**: Systems frequently mask offline models with hardcoded canned text without transparent indicators.

**RAG-QA** resolves these challenges by introducing a multi-stage, grounded pipeline that combines **FAISS Dense Retrieval**, **BM25Plus Lexical Retrieval**, **Reciprocal Rank Fusion (RRF)**, **CrossEncoder Reranking**, **Prompt Injection Delimitation**, **Post-Generation Faithfulness Verification**, and **Honest Degraded-Mode Labeling**.

---

## 2. Key Objectives & Features

1. **Multi-Format Ingestion**: Validates, sanitizes, and parses PDF (PyMuPDF with PyTesseract OCR fallback), DOCX (python-docx), and TXT documents.
2. **Token-Aware Structural Chunking**: Respects paragraph boundaries and sentence splits with configurable token budgets (default 500 tokens) and overlap.
3. **Dual Hybrid Retrieval**: Parallel FAISS inner-product vector search (`all-MiniLM-L6-v2`) and Rank-BM25Plus keyword search merged via Reciprocal Rank Fusion ($c=60$).
4. **CrossEncoder Reranking**: Uses `cross-encoder/ms-marco-MiniLM-L-6-v2` to score query-passage interactions and filter weak candidates.
5. **Document Scope Filtering**: Users can restrict retrieval to a specific document or query the entire multi-document knowledge base.
6. **Conversation-Aware Query Rewriting**: Resolves anaphoric pronouns and follow-up ambiguities across conversational turns.
7. **Prompt Injection Defense**: Strictly isolates retrieved document passages inside `<evidence>` blocks as untrusted data.
8. **Faithfulness & Evidence Verification**: Evaluates lexical support and assigns explicit status badges (`HIGH EVIDENCE`, `MEDIUM EVIDENCE`, `LOW EVIDENCE`, `INSUFFICIENT EVIDENCE`).
9. **Explicit Abstention**: Explicitly abstains when sufficient information was not found rather than inventing an answer.
10. **Research Ablation Suite**: Live benchmarking framework answering research questions RQ1 through RQ5 across Hit Rate, MRR, Faithfulness, Answer Relevance, and Latency.
11. **Comprehensive Health Telemetry**: `GET /api/health` endpoint monitoring database, embeddings, FAISS, BM25, reranker, LLM reachability, and index manifest integrity.

---

## 3. System Architecture

```text
               +-------------------------------------------------------+
               |                  USER INTERFACE                       |
               |  (Dashboard, Chat, Scope Filter, Source Viewer, Eval) |
               +---------------------------+---------------------------+
                                           | HTTP / REST API
               +---------------------------v---------------------------+
               |                     FLASK REST API                    |
               |  /api/documents/*  |  /api/chat  |  /api/health       |
               |  /api/analytics    |  /api/feedback | /api/evaluation |
               +---------------------------+---------------------------+
                                           |
               +---------------------------v---------------------------+
               |                    QUERY PIPELINE                     |
               |                                                       |
               |  1. Conversation-Aware Query Rewriting                |
               |  2. Document Scope Filtering (Optional Target Doc)    |
               |  3. Dense Retrieval (FAISS) + Sparse (BM25Plus)       |
               |  4. Reciprocal Rank Fusion (RRF Constant c=60)        |
               |  5. CrossEncoder Reranking (ms-marco-MiniLM-L-6-v2)  |
               |  6. Evidence Filtering (Score Thresholding)          |
               |  7. Untrusted Data Delimitation & Prompt Defense      |
               |  8. Grounded LLM Generation (Ollama/OpenAI/Local)     |
               |  9. Faithfulness & Evidence Verification              |
               +---------------------------+---------------------------+
                                           |
               +---------------------------v---------------------------+
               |              DATA STORES & MODEL SERVICES             |
               |                                                       |
               |  - SQLite (WAL Mode): Documents, Chunks, Queries      |
               |  - FAISS FlatIP: 384-dim Dense Vector Store           |
               |  - BM25Plus: Inverted Keyword Index                   |
               |  - Index Manifest: Model Drift & Integrity Tracking   |
               |  - SentenceTransformers: Embedding & CrossEncoder     |
               +-------------------------------------------------------+
```

---

## 4. Hardware & Software Requirements

- **Operating System**: Windows 10/11, macOS, or Linux.
- **Python**: Version 3.10 or 3.11.
- **RAM**: Minimum 8 GB (16 GB recommended for running local LLMs).
- **Disk**: ~2 GB free disk space for HuggingFace model cache and index storage.

---

## 5. Installation & Setup

### Step 1: Clone the Repository & Create Virtual Environment
```bash
git clone <repo-url>
cd RAG
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### Step 2: Install Python Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
copy .env.example .env
```
To enable a real generative LLM, choose one of the following configurations in your `.env`:

* **Option A: Ollama (Free, Local, Offline)**
  ```ini
  LLM_PROVIDER=openai_compatible
  LLM_BASE_URL=http://localhost:11434/v1
  LLM_MODEL_NAME=phi3:mini
  LLM_API_KEY=none
  ```

* **Option B: Groq (Ultra-Fast Free Tier)**
  ```ini
  LLM_PROVIDER=openai_compatible
  LLM_BASE_URL=https://api.groq.com/openai/v1
  LLM_MODEL_NAME=llama-3.1-8b-instant
  LLM_API_KEY=your_groq_api_key_here
  ```

* **Option C: OpenAI**
  ```ini
  LLM_PROVIDER=openai_compatible
  LLM_BASE_URL=https://api.openai.com/v1
  LLM_MODEL_NAME=gpt-4o-mini
  LLM_API_KEY=your_openai_api_key_here
  ```

* **Option D: Offline Demonstration Default**
  ```ini
  LLM_PROVIDER=local_mock
  ```
  *(Runs locally with transparent `[SYSTEM NOTICE: Generated in DEGRADED MODE]` labeling)*.

### Step 4: Run Automated Tests
```bash
python -m pytest -v
```
*(All 20 tests should pass)*.

### Step 5: Start the Application Server
```bash
python run.py
```
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 6. REST API Documentation

### Documents
- `POST /api/documents/upload`: Upload PDF, DOCX, or TXT file (multipart/form-data).
- `GET /api/documents`: List all uploaded documents with status and chunk counts.
- `GET /api/documents/<id>`: Retrieve document metadata and its individual chunks.
- `DELETE /api/documents/<id>`: Delete document and automatically rebuild vector & BM25 indices.
- `POST /api/documents/<id>/reindex`: Re-parse and rebuild chunks & vectors for a specific document.
- `POST /api/documents/rebuild`: Rebuild entire FAISS and BM25 index from scratch.

### Chat & Q&A
- `POST /api/chat`: Submit natural-language question.
  - Body: `{"question": "...", "conversation_id": "optional", "document_ids": ["doc-id"]}`
  - Response: Grounded answer, evidence status badge, citations with passage text, latency metrics, and active LLM provider.
- `GET /api/conversations`: List all conversation threads.
- `GET /api/conversations/<id>`: Get all messages for a specific conversation.
- `DELETE /api/conversations/<id>`: Delete conversation thread.
- `GET /api/sources/<chunk_id>`: Retrieve full passage details for a citation.

### Analytics, Health & Evaluation
- `GET /api/health`: Component-level health check (database, FAISS, BM25, embeddings, reranker, LLM, manifest).
- `GET /api/analytics`: Aggregate metrics (doc count, query count, average latency, evidence distribution, feedback stats).
- `POST /api/feedback`: Submit user satisfaction rating (1 = Helpful, 0 = Not Helpful).
- `POST /api/evaluation/run`: Execute the 84-sample comparative ablation suite.
- `GET /api/evaluation/history`: View past benchmark executions.

---

## 7. Demonstration Guide

1. **Upload & Indexing**: Navigate to the **Documents** tab. Upload a sample PDF or TXT file. Notice the page count and chunk count populate immediately.
2. **Inspect Chunks**: Click **View Chunks** on any document row to inspect how text elements were chunked with preserved metadata.
3. **Factual Question Answering**: In the **Q&A Chat** tab, ask a factual question related to the uploaded document. Observe the **Evidence Status Badge** and **Grounded Evidence Sources**.
4. **Citation Inspection**: Click **Inspect** on any source pill to open the passage modal showing exact document, page number, and text.
5. **Conversational Follow-Up**: Ask a follow-up pronoun question (e.g., *"What are its primary benefits?"*). The system re-writes the query incorporating prior turns before retrieval.
6. **Query Scoping**: Select a specific document from the **Retrieval Scope** dropdown and query against only that file.
7. **Abstention Test**: Ask a question whose topic is entirely absent from the documents (e.g., *"Who was the 16th president of Mars?"*). The system safely abstains with `INSUFFICIENT EVIDENCE`.
8. **Research Ablation Benchmark**: Navigate to the **Research & Ablation** tab and click **Run Benchmark Suite** to evaluate Baseline Dense vs. Hybrid vs. Reranked vs. Full Pipeline across 84 test cases.

---

## 8. Final-Year Viva Technical Reference

### Core Architecture Concepts
- **Dense vs. Sparse Search**: Dense vector search captures deep semantic similarity and paraphrasing, whereas BM25Plus captures exact jargon, keywords, and IDs.
- **Reciprocal Rank Fusion (RRF)**: Merges ranked lists using $RRF(d) = \sum \frac{1}{60 + rank(d)}$, normalizing differences in score scales between cosine/inner-product similarity and BM25 scores.
- **Cross-Encoder Reranking**: Unlike bi-encoders that encode queries and documents independently, the Cross-Encoder processes `(Query, Passage)` simultaneously through full multi-head self-attention, generating precise relevance logits.
- **Prompt Injection Defense**: All retrieved passages are isolated inside clear delimited boundary tags and instructed to be treated as untrusted reference data, defeating attempts by documents to override system directives.
