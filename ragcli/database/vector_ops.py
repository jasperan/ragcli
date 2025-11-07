"""Vector operations for Oracle DB 26ai in ragcli."""

import uuid
import json
from typing import List, Tuple, Dict, Any, Optional
import oracledb

def generate_id() -> str:
    """Generate UUID for IDs."""
    return str(uuid.uuid4())

def insert_document(
    conn: oracledb.Connection,
    filename: str,
    file_format: str,
    file_size_bytes: int,
    extracted_text_size_bytes: Optional[int],
    chunk_count: int,
    total_tokens: int,
    embedding_dimension: int = 768,
    ocr_processed: str = 'N',
    metadata: Dict = None
) -> str:
    """Insert a new document and return its ID."""
    doc_id = generate_id()
    metadata_json = json.dumps(metadata or {})
    
    approx_emb_size = chunk_count * embedding_dimension * 4  # bytes, float32
    
    sql = """
    INSERT INTO DOCUMENTS (
        document_id, filename, file_format, file_size_bytes, extracted_text_size_bytes,
        chunk_count, total_tokens, embedding_dimension, approximate_embedding_size_bytes,
        ocr_processed, metadata_json
    ) VALUES (
        :doc_id, :filename, :file_format, :file_size_bytes, :extracted_size,
        :chunk_count, :total_tokens, :dim, :approx_size, :ocr,
        :metadata
    )
    """
    cursor = conn.cursor()
    cursor.execute(sql, {
        'doc_id': doc_id,
        'filename': filename,
        'file_format': file_format,
        'file_size_bytes': file_size_bytes,
        'extracted_size': extracted_text_size_bytes,
        'chunk_count': chunk_count,
        'total_tokens': total_tokens,
        'dim': embedding_dimension,
        'approx_size': approx_emb_size,
        'ocr': ocr_processed,
        'metadata': metadata_json
    })
    conn.commit()
    return doc_id

def insert_chunk(
    conn: oracledb.Connection,
    doc_id: str,
    chunk_number: int,
    chunk_text: str,
    token_count: int,
    character_count: int,
    start_pos: int = 0,
    end_pos: int = 0,
    embedding: List[float] = None,
    embedding_model: str = "nomic-embed-text"
) -> str:
    """Insert a chunk with embedding."""
    chunk_id = generate_id()
    
    sql = """
    INSERT INTO CHUNKS (
        chunk_id, document_id, chunk_number, chunk_text, token_count,
        character_count, start_position, end_position, chunk_embedding, embedding_model
    ) VALUES (
        :chunk_id, :doc_id, :chunk_num, :text, :token_count,
        :char_count, :start, :end, VECTOR(:embedding, FLOAT32), :model
    )
    """
    cursor = conn.cursor()
    cursor.execute(sql, {
        'chunk_id': chunk_id,
        'doc_id': doc_id,
        'chunk_num': chunk_number,
        'text': chunk_text,
        'token_count': token_count,
        'char_count': character_count,
        'start': start_pos,
        'end': end_pos,
        'embedding': embedding or [],
        'model': embedding_model
    })
    conn.commit()
    return chunk_id

def search_similar(
    conn: oracledb.Connection,
    query_embedding: List[float],
    top_k: int = 5,
    min_similarity: float = 0.5,
    document_ids: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """Search for similar chunks using vector similarity."""
    sql_base = """
    SELECT c.chunk_id, c.document_id, c.chunk_text, c.chunk_number,
           VECTOR_DISTANCE(c.chunk_embedding, VECTOR(:query_emb, FLOAT32), COSINE) AS similarity_score
    FROM CHUNKS c
    """
    if document_ids:
        doc_ids_str = ",".join(f"'{doc_id}'" for doc_id in document_ids)
        sql_base += f" WHERE c.document_id IN ({doc_ids_str}) "
    
    sql = sql_base + """
    ORDER BY similarity_score ASC  -- Cosine distance, lower is more similar
    FETCH FIRST :top_k ROWS ONLY
    """
    
    cursor = conn.cursor()
    cursor.execute(sql, {'query_emb': query_embedding, 'top_k': top_k})
    
    results = []
    for row in cursor:
        score = 1 - row[4]  # Convert distance to similarity (cosine similarity = 1 - distance)
        if score >= min_similarity:
            results.append({
                'chunk_id': row[0],
                'document_id': row[1],
                'chunk_number': row[2],
                'text': row[3][:200] + '...' if len(row[3]) > 200 else row[3],  # Excerpt
                'similarity_score': score
            })
    
    return results

# TODO: Add query logging to QUERIES/QUERY_RESULTS, auto-index creation based on chunk count, batch inserts, retries
