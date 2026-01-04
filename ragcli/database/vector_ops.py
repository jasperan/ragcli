"""Vector operations for Oracle DB 26ai in ragcli."""

import uuid
import json
from typing import List, Tuple, Dict, Any, Optional
import oracledb
from ..utils.logger import get_logger

logger = get_logger(__name__)

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
        :v_doc_id, :v_filename, :v_file_format, :v_file_size_bytes, :v_extracted_size,
        :v_chunk_count, :v_total_tokens, :v_dim, :v_approx_size, :v_ocr,
        :v_metadata
    )
    """
    cursor = conn.cursor()
    cursor.execute(sql, {
        'v_doc_id': doc_id,
        'v_filename': filename,
        'v_file_format': file_format,
        'v_file_size_bytes': file_size_bytes,
        'v_extracted_size': extracted_text_size_bytes,
        'v_chunk_count': chunk_count,
        'v_total_tokens': total_tokens,
        'v_dim': embedding_dimension,
        'v_approx_size': approx_emb_size,
        'v_ocr': ocr_processed,
        'v_metadata': metadata_json
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
        :v_chunk_id, :v_doc_id, :v_chunk_num, :v_text, :v_token_count,
        :v_char_count, :v_start, :v_end, TO_VECTOR(:v_embedding), :v_model
    )
    """
    cursor = conn.cursor()
    cursor.execute(sql, {
        'v_chunk_id': chunk_id,
        'v_doc_id': doc_id,
        'v_chunk_num': chunk_number,
        'v_text': chunk_text,
        'v_token_count': token_count,
        'v_char_count': character_count,
        'v_start': start_pos,
        'v_end': end_pos,
        'v_embedding': json.dumps(embedding or []),
        'v_model': embedding_model
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
           VECTOR_DISTANCE(c.chunk_embedding, TO_VECTOR(:v_query_emb), COSINE) AS similarity_score
    FROM CHUNKS c
    """
    if document_ids:
        doc_ids_str = ",".join(f"'{doc_id}'" for doc_id in document_ids)
        sql_base += f" WHERE c.document_id IN ({doc_ids_str}) "
    
    sql = sql_base + """
    ORDER BY similarity_score ASC
    FETCH FIRST :v_top_k ROWS ONLY
    """
    
    cursor = conn.cursor()
    cursor.execute(sql, {
        'v_query_emb': json.dumps(query_embedding),
        'v_top_k': top_k
    })
    
    results = []
    for row in cursor:
        score = 1 - row[4]  # Convert distance to similarity (cosine similarity = 1 - distance)
        if score >= min_similarity:
            chunk_text_val = str(row[2]) if row[2] else ""
            results.append({
                'chunk_id': row[0],
                'document_id': row[1],
                'chunk_number': row[3],
                'text': chunk_text_val,
                'similarity_score': score
            })
    
    return results


def create_vector_index(conn: oracledb.Connection, config: Dict[str, Any]) -> None:
    """Create vector index based on chunk count and configuration."""
    # Check if index already exists
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT index_name FROM user_indexes WHERE index_name = 'CHUNKS_EMBEDDING_IDX'")
        if cursor.fetchone():
            logger.info("Vector index already exists, skipping creation")
            return
    except:
        pass  # Index doesn't exist, continue

    # Get chunk count to determine index type
    cursor.execute("SELECT COUNT(*) FROM CHUNKS")
    chunk_count = cursor.fetchone()[0]

    # Auto-select index type based on chunk count (from spec)
    if chunk_count <= 1000:
        index_type = "IVF_FLAT"
        index_params = ""
    elif chunk_count <= 100000:
        index_type = "HNSW"
        index_params = "WITH (m=16, ef_construction=200)"
    else:
        index_type = "HYBRID"
        index_params = "WITH (m=16, ef_construction=200)"

    # Get accuracy from config
    accuracy = config.get('vector_index', {}).get('accuracy', 95)

    # Create index
    index_sql = f"""
    CREATE VECTOR INDEX CHUNKS_EMBEDDING_IDX
    ON CHUNKS(chunk_embedding)
    ORGANIZATION CLUSTER
    WITH TARGET ACCURACY {accuracy}
    {index_params}
    DISTANCE METRIC COSINE
    """

    try:
        logger.info(f"Creating {index_type} vector index for {chunk_count} chunks")
        cursor.execute(index_sql)
        conn.commit()
        logger.info(f"Vector index created successfully: {index_type}")
    except Exception as e:
        logger.error(f"Failed to create vector index: {e}", exc_info=True)
        # Don't raise - index creation failure shouldn't stop the app
        conn.rollback()


def log_query(
    conn: oracledb.Connection,
    query_text: str,
    query_embedding: List[float],
    selected_documents: Optional[List[str]],
    top_k: int,
    similarity_threshold: float,
    results: List[Dict[str, Any]],
    response_text: str,
    response_tokens: int,
    timing: Dict[str, float]
) -> str:
    """Log query and results to database."""
    query_id = generate_id()

    # Insert query
    sql = """
    INSERT INTO QUERIES (
        query_id, query_text, query_embedding, selected_documents, top_k,
        similarity_threshold, response_text, response_tokens,
        embedding_time_ms, search_time_ms, generation_time_ms
    ) VALUES (
        :v_query_id, :v_query_text, TO_VECTOR(:v_query_emb), :v_docs, :v_top_k,
        :v_threshold, :v_response, :v_resp_tokens,
        :v_emb_time, :v_search_time, :v_gen_time
    )
    """

    docs_str = ",".join(selected_documents) if selected_documents else None

    cursor = conn.cursor()
    cursor.execute(sql, {
        'v_query_id': query_id,
        'v_query_text': query_text,
        'v_query_emb': json.dumps(query_embedding),
        'v_docs': docs_str,
        'v_top_k': top_k,
        'v_threshold': similarity_threshold,
        'v_response': response_text,
        'v_resp_tokens': response_tokens,
        'v_emb_time': timing.get('embedding_time_ms', 0),
        'v_search_time': timing.get('search_time_ms', 0),
        'v_gen_time': timing.get('generation_time_ms', 0)
    })

    # Insert query results
    for result in results[:top_k]:  # Only log top-k results
        result_sql = """
        INSERT INTO QUERY_RESULTS (
            result_id, query_id, chunk_id, similarity_score, rank
        ) VALUES (
            :result_id, :query_id, :chunk_id, :score, :rank
        )
        """
        cursor.execute(result_sql, {
            'result_id': generate_id(),
            'query_id': query_id,
            'chunk_id': result['chunk_id'],
            'score': result['similarity_score'],
            'rank': results.index(result) + 1
        })

    conn.commit()
    return query_id


# TODO: Batch inserts, retries, index maintenance
