-- RAG-QA SQLite Database Schema

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    file_hash TEXT NOT NULL UNIQUE,
    file_type TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    page_count INTEGER DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'uploaded', -- uploaded, indexing, indexed, error
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_documents_file_hash ON documents(file_hash);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    page_number INTEGER DEFAULT 1,
    section TEXT DEFAULT 'Body',
    text TEXT NOT NULL,
    token_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_chunk_idx ON chunks(document_id, chunk_index);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT 'New Conversation',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL, -- 'user' or 'assistant'
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);

CREATE TABLE IF NOT EXISTS queries (
    id TEXT PRIMARY KEY,
    conversation_id TEXT,
    original_question TEXT NOT NULL,
    rewritten_question TEXT,
    answer TEXT NOT NULL,
    evidence_status TEXT NOT NULL, -- HIGH EVIDENCE, MEDIUM EVIDENCE, LOW EVIDENCE, INSUFFICIENT EVIDENCE
    retrieval_latency REAL DEFAULT 0.0,
    generation_latency REAL DEFAULT 0.0,
    total_latency REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_queries_conversation ON queries(conversation_id);

CREATE TABLE IF NOT EXISTS retrieval_results (
    id TEXT PRIMARY KEY,
    query_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    retrieval_method TEXT NOT NULL, -- 'dense', 'bm25', 'hybrid'
    initial_score REAL DEFAULT 0.0,
    rerank_score REAL DEFAULT 0.0,
    rank INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(query_id) REFERENCES queries(id) ON DELETE CASCADE,
    FOREIGN KEY(chunk_id) REFERENCES chunks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_retrieval_query ON retrieval_results(query_id);

CREATE TABLE IF NOT EXISTS evaluations (
    id TEXT PRIMARY KEY,
    pipeline_name TEXT NOT NULL,
    num_samples INTEGER NOT NULL,
    mean_hit_rate REAL NOT NULL,
    mean_mrr REAL NOT NULL,
    mean_faithfulness REAL NOT NULL,
    mean_answer_relevance REAL NOT NULL,
    mean_latency REAL NOT NULL,
    detailed_results TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS feedback (
    id TEXT PRIMARY KEY,
    query_id TEXT NOT NULL,
    rating INTEGER NOT NULL, -- 1 for helpful, 0 for not helpful
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(query_id) REFERENCES queries(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_feedback_query ON feedback(query_id);

