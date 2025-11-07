"""Database schema definitions for ragcli."""

DOCUMENTS_TABLE = """
CREATE TABLE DOCUMENTS (
    document_id         VARCHAR2(36) PRIMARY KEY,
    filename            VARCHAR2(512) NOT NULL,
    file_format         VARCHAR2(10) NOT NULL,  -- TXT, MD, PDF
    file_size_bytes     NUMBER NOT NULL,
    extracted_text_size_bytes NUMBER,
    upload_timestamp    TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
    last_modified       TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
    chunk_count         NUMBER NOT NULL,
    total_tokens        NUMBER NOT NULL,
    embedding_dimension NUMBER DEFAULT 768,
    approximate_embedding_size_bytes NUMBER,
    ocr_processed       VARCHAR2(1) DEFAULT 'N',
    status              VARCHAR2(20) DEFAULT 'READY',  -- PROCESSING, READY, ERROR
    metadata_json       CLOB,
    created_at          TIMESTAMP DEFAULT SYSTIMESTAMP,
    updated_at          TIMESTAMP DEFAULT SYSTIMESTAMP
);
"""

CHUNKS_TABLE = """
CREATE TABLE CHUNKS (
    chunk_id            VARCHAR2(36) PRIMARY KEY,
    document_id         VARCHAR2(36) NOT NULL,
    chunk_number        NUMBER NOT NULL,
    chunk_text          CLOB NOT NULL,
    token_count         NUMBER NOT NULL,
    character_count     NUMBER NOT NULL,
    start_position      NUMBER,
    end_position        NUMBER,
    chunk_embedding     VECTOR(768, FLOAT32),
    embedding_model     VARCHAR2(50),
    created_at          TIMESTAMP DEFAULT SYSTIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES DOCUMENTS(document_id) ON DELETE CASCADE,
    CONSTRAINT unique_chunk_per_doc UNIQUE(document_id, chunk_number)
);
"""

QUERIES_TABLE = """
CREATE TABLE QUERIES (
    query_id            VARCHAR2(36) PRIMARY KEY,
    query_text          CLOB NOT NULL,
    query_embedding     VECTOR(768, FLOAT32),
    embedding_model     VARCHAR2(50),
    selected_documents  VARCHAR2(2000),  -- Comma-separated doc IDs
    top_k               NUMBER DEFAULT 5,
    similarity_threshold NUMBER DEFAULT 0.5,
    response_text       CLOB,
    response_tokens     NUMBER,
    response_time_ms    NUMBER,
    embedding_time_ms   NUMBER,
    search_time_ms      NUMBER,
    generation_time_ms  NUMBER,
    retrieved_chunks    VARCHAR2(4000),  -- JSON: chunk IDs and scores
    status              VARCHAR2(20),    -- SUCCESS, FAILED, PARTIAL
    error_message       VARCHAR2(500),
    created_at          TIMESTAMP DEFAULT SYSTIMESTAMP
);
"""

QUERY_RESULTS_TABLE = """
CREATE TABLE QUERY_RESULTS (
    result_id           VARCHAR2(36) PRIMARY KEY,
    query_id            VARCHAR2(36) NOT NULL,
    chunk_id            VARCHAR2(36) NOT NULL,
    similarity_score    FLOAT,
    rank                NUMBER,
    created_at          TIMESTAMP DEFAULT SYSTIMESTAMP,
    FOREIGN KEY (query_id) REFERENCES QUERIES(query_id) ON DELETE CASCADE,
    FOREIGN KEY (chunk_id) REFERENCES CHUNKS(chunk_id) ON DELETE CASCADE
);
"""

VECTOR_INDEX = """
CREATE VECTOR INDEX CHUNKS_EMBEDDING_IDX 
ON CHUNKS(chunk_embedding) ORGANIZATION CLUSTER 
WITH TARGET ACCURACY 95
DISTANCE METRIC COSINE;
"""

def get_create_schemas_sql() -> list:
    """Return list of SQL statements to create schemas."""
    return [
        DOCUMENTS_TABLE,
        CHUNKS_TABLE,
        QUERIES_TABLE,
        QUERY_RESULTS_TABLE,
        VECTOR_INDEX,
    ]

# TODO: Auto-select index type based on data size (HNSW/IVF/HYBRID)
