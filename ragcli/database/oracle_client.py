"""Oracle Database 26ai client for ragcli."""

import oracledb
from typing import Optional
from .schemas import get_create_schemas_sql
import oracledb
from typing import List

class OracleClient:
    def __init__(self, config: dict):
        self.config = config
        self.pool = None
        self._connect()
    
    def _connect(self):
        """Establish connection pool."""
        username = self.config['oracle']['username']
        password = self.config['oracle']['password']
        dsn = self.config['oracle']['dsn']
        pool_size = self.config['oracle'].get('pool_size', 10)
        
        # TODO: Add TLS config if use_tls
        self.pool = oracledb.create_pool(
            user=username,
            password=password,
            dsn=dsn,
            min=1,
            max=pool_size,
            increment=1
        )
    
    def get_connection(self) -> oracledb.Connection:
        """Get a connection from the pool."""
        return self.pool.acquire()
    
    def init_db(self):
        """Initialize database schemas and indexes if they don't exist."""
        conn = self.get_connection()
        cursor = conn.cursor()
        tables = [
            ("DOCUMENTS", """
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
"""),
            ("CHUNKS", """
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
"""),
            ("QUERIES", """
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
"""),
            ("QUERY_RESULTS", """
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
""")
        ]
        
        created_something = False
        
        try:
            # Create tables if they don't exist
            for table_name, create_sql in tables:
                cursor.execute(f"SELECT COUNT(*) FROM USER_TABLES WHERE TABLE_NAME = '{table_name}'")
                if cursor.fetchone()[0] == 0:
                    cursor.execute(create_sql)
                    created_something = True
            
            # Create vector index if it doesn't exist
            cursor.execute("SELECT COUNT(*) FROM USER_INDEXES WHERE INDEX_NAME = 'CHUNKS_EMBEDDING_IDX'")
            if cursor.fetchone()[0] == 0:
                index_sql = """
CREATE VECTOR INDEX CHUNKS_EMBEDDING_IDX 
ON CHUNKS(chunk_embedding) ORGANIZATION CLUSTER 
WITH TARGET ACCURACY 95
DISTANCE METRIC COSINE;
"""
                cursor.execute(index_sql)
                created_something = True
            
            if created_something:
                conn.commit()
                print("Database schemas and indexes created successfully.")
            else:
                print("Database already initialized.")
                
        except oracledb.Error as e:
            conn.rollback()
            raise Exception(f"Failed to initialize database: {e}")
        finally:
            cursor.close()
            conn.close()
    
    def close(self):
        """Close the pool."""
        if self.pool:
            self.pool.close()

# TODO: Implement retries in _connect(), auto-index selection based on data size
