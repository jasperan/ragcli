"""Main RAG orchestration for ragcli."""

import hashlib
import logging
import time
from typing import Dict, List, Any, Optional
from .document_processor import preprocess_document, chunk_text, get_document_metadata
from .embedding import generate_embedding, generate_response
from .similarity_search import search_chunks as _search_chunks_internal
from ..database.vector_ops import insert_document, insert_chunks_batch, log_query, find_document_by_hash
from ..database.oracle_client import OracleClient
from ..config.config_manager import load_config
from ..memory.session import SessionManager
from ..memory.rewriter import QueryRewriter
from ..memory.context import ContextManager
from ..knowledge.extractor import EntityExtractor
from ..knowledge.graph_store import GraphStore
from pathlib import Path

logger = logging.getLogger(__name__)

def upload_document(file_path: str, config: Optional[dict] = None, progress=None) -> Dict[str, Any]:
    """Upload and process a document with optional progress tracking.

    Args:
        file_path: Path to document file
        config: Configuration dict
        progress: Optional Rich Progress instance for tracking

    Returns:
        Document metadata dict
    """
    if config is None:
        config = load_config()

    start_time = time.perf_counter()

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    file_format = path.suffix.lstrip('.').lower()
    if file_format not in config['documents']['supported_formats']:
        raise ValueError(f"Unsupported format: {file_format}")

    file_size = path.stat().st_size

    if file_size > config['documents']['max_file_size_mb'] * 1024 * 1024:
        raise ValueError("File too large")

    client = OracleClient(config)
    conn = None
    process_task = None
    try:
        conn = client.get_connection()

        if progress:
            process_task = progress.add_task(f"[cyan]Processing {path.name}...", total=100)
            progress.update(process_task, completed=10)

        text, ocr_used = preprocess_document(file_path, config, conn=conn)
        ocr_processed = 'Y' if ocr_used else 'N'

        # Deduplication: check content hash before expensive embedding
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        try:
            existing_id = find_document_by_hash(conn, content_hash)
        except Exception:
            existing_id = None  # column may not exist yet; skip dedup
        if existing_id:
            logger.info(f"Duplicate detected: {path.name} matches document {existing_id}")
            if conn: conn.close()
            client.close()
            return {
                'document_id': existing_id,
                'filename': path.name,
                'file_format': file_format,
                'file_size_bytes': file_size,
                'duplicate': True,
                'duplicate_of': existing_id,
                'upload_time_ms': (time.perf_counter() - start_time) * 1000,
            }

        if progress:
            progress.update(process_task, completed=30, description=f"[cyan]Chunking {path.name}...")

        chunks = chunk_text(text, config, conn=conn)
        doc_meta = get_document_metadata(text, chunks, ocr_used)

        if progress:
            progress.update(process_task, completed=50, description="[cyan]Creating embeddings...")

        doc_id = insert_document(
            conn, path.name, file_format.upper(), file_size, doc_meta['extracted_text_size_bytes'],
            doc_meta['chunk_count'], doc_meta['total_tokens'], config['vector_index']['dimension'], ocr_processed,
            content_hash=content_hash,
        )

        embedding_model = config['ollama']['embedding_model']
        total_chunks = len(chunks)

        # Generate embeddings (still sequential HTTP, but with connection reuse)
        for i, chunk_data in enumerate(chunks):
            chunk_data['embedding'] = generate_embedding(
                chunk_data['text'], embedding_model, config, conn=conn
            )
            chunk_data['chunk_number'] = i + 1

            if progress:
                chunk_progress = 50 + int((i + 1) / total_chunks * 45)
                progress.update(
                    process_task,
                    completed=chunk_progress,
                    description=f"[cyan]Embedding chunk {i+1}/{total_chunks}..."
                )

        # Batch insert all chunks in a single DB round-trip
        if progress:
            progress.update(process_task, completed=95, description="[cyan]Writing to database...")
        insert_chunks_batch(conn, doc_id, chunks, embedding_model=embedding_model)

        conn.commit()

        # Knowledge graph extraction (non-blocking, non-fatal)
        _extract_knowledge_graph(conn, doc_id, config)

    except Exception as e:
        if conn: conn.rollback()
        raise e
    finally:
        if conn: conn.close()
        client.close()

    if progress and process_task is not None:
        progress.update(process_task, completed=100, description=f"[green]✓ {path.name} uploaded")
        progress.remove_task(process_task)

    total_time = time.perf_counter() - start_time

    return {
        'document_id': doc_id,
        'filename': path.name,
        'file_format': file_format,
        'file_size_bytes': file_size,
        **doc_meta,
        'embedding_dimension': config['vector_index']['dimension'],
        'approximate_embedding_size_bytes': doc_meta['chunk_count'] * config['vector_index']['dimension'] * 4,
        'upload_time_ms': total_time * 1000
    }


# Backwards-compatible alias
upload_document_with_progress = upload_document


def _extract_knowledge_graph(conn, doc_id: str, config: dict):
    """Extract entities and relationships from document chunks into the KG. Non-fatal."""
    kg_config = config.get('knowledge_graph', {})
    if not kg_config.get('enabled', True):
        return

    try:
        extractor = EntityExtractor(config)
        graph_store = GraphStore(conn)

        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT chunk_id, chunk_text FROM CHUNKS WHERE document_id = :doc_id ORDER BY chunk_number",
                {"doc_id": doc_id}
            )
            doc_chunks = cursor.fetchall()

        for chunk_id, chunk_content in doc_chunks:
            # Oracle CLOB columns return LOB objects; convert to str
            if hasattr(chunk_content, 'read'):
                chunk_content = chunk_content.read()
            extraction = extractor.extract_from_text(chunk_content)
            if extraction:
                for entity in extraction.get('entities', []):
                    entity_id = graph_store.upsert_entity(
                        name=entity['name'],
                        entity_type=entity['type'],
                        description=entity.get('description', ''),
                        doc_id=doc_id
                    )
                    graph_store.link_entity_chunk(entity_id, chunk_id)

                for rel in extraction.get('relationships', []):
                    source_id = graph_store.upsert_entity(
                        name=rel['source'], entity_type='UNKNOWN',
                        description='', doc_id=doc_id
                    )
                    target_id = graph_store.upsert_entity(
                        name=rel['target'], entity_type='UNKNOWN',
                        description='', doc_id=doc_id
                    )
                    graph_store.insert_relationship(
                        source_id, target_id, rel['type'],
                        rel.get('description', ''), chunk_id, doc_id
                    )

        conn.commit()
        logger.info(f"Knowledge graph extraction complete for document {doc_id}")
    except Exception as e:
        logger.warning(f"Knowledge graph extraction failed (non-fatal): {e}")


def ask_query(
    query: str,
    document_ids: Optional[List[str]] = None,
    top_k: Optional[int] = None,
    min_similarity: Optional[float] = None,
    config: Optional[dict] = None,
    stream: bool = False,
    include_embeddings: bool = False,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Ask a query using RAG."""
    if config is None:
        config = load_config()

    top_k = top_k or config['rag']['top_k']
    min_similarity = min_similarity or config['rag']['min_similarity_score']

    start_time = time.perf_counter()

    # Session handling
    original_query = query
    trace_id = None

    # Use a single OracleClient for all DB operations in this query
    client = OracleClient(config)
    try:
        if session_id:
            conn = client.get_connection()
            try:
                session_mgr = SessionManager(conn)
                session_mgr.touch(session_id)

                recent_turns = session_mgr.get_recent_turns(
                    session_id,
                    limit=config.get('memory', {}).get('max_recent_turns', 5)
                )
                summary = session_mgr.get_summary(session_id)

                if recent_turns:
                    rewriter = QueryRewriter(config)
                    query = rewriter.rewrite(query, recent_turns, summary)
            finally:
                conn.close()

        # Search — pass a connection from our pool to avoid creating another pool
        search_conn = client.get_connection()
        try:
            search_result = _search_chunks_internal(
                query, top_k, min_similarity, document_ids, config, conn=search_conn,
            )
        finally:
            search_conn.close()
        results = search_result['results']
        search_metrics = search_result['metrics']

        # Assemble context
        context = "\n\n".join([f"From {r['document_id']}: {r['text']}" for r in results])

        # RAG prompt
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Use the following context to answer the user's question accurately. If the context doesn't contain relevant information, say so."},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}
        ]

        # Generate response
        gen_start = time.perf_counter()
        if stream:
            response_generator = generate_response(messages, config['ollama']['chat_model'], config, stream=True)
            response = "".join(response_generator)
        else:
            response = generate_response(messages, config['ollama']['chat_model'], config, stream=False)
        gen_time = time.perf_counter() - gen_start

        total_time = time.perf_counter() - start_time

        # Log query and store session turn using a single connection
        log_timing = {
            'embedding_time_ms': search_metrics.get('embedding_time_ms', 0),
            'search_time_ms': search_metrics.get('search_time_ms', 0),
            'generation_time_ms': gen_time * 1000,
            'total_time_ms': total_time * 1000,
        }

        conn = client.get_connection()
        try:
            log_query(
                conn, query, search_result['query_embedding'], document_ids, top_k,
                min_similarity, results, response, len(response.split()), log_timing
            )

            if session_id:
                session_mgr = SessionManager(conn)
                chunk_ids = [r.get('chunk_id') for r in results if r.get('chunk_id')]
                turn_number = session_mgr.get_turn_count(session_id) + 1
                session_mgr.add_turn(
                    session_id, turn_number, original_query,
                    rewritten_query=query if query != original_query else None,
                    response=response, trace_id=trace_id, chunk_ids=chunk_ids
                )

                turn_count = session_mgr.get_turn_count(session_id)
                ctx_mgr = ContextManager(config)
                if ctx_mgr.should_summarize(turn_count):
                    all_turns = session_mgr.get_recent_turns(session_id, limit=turn_count)
                    existing_summary = session_mgr.get_summary(session_id)
                    new_summary = ctx_mgr.summarize(all_turns, existing_summary)
                    session_mgr.update_summary(session_id, new_summary)
        finally:
            conn.close()
    finally:
        client.close()

    # Simple token estimate
    prompt_tokens = len(query.split()) + len(context.split())
    completion_tokens = len(response.split())

    response_data = {
        'response': response,
        'results': results,
        'session_id': session_id,
        'trace_id': trace_id,
        'metrics': {
            'search_time_ms': search_metrics.get('search_time_ms', 0),
            'generation_time_ms': gen_time * 1000,
            'total_time_ms': total_time * 1000,
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': prompt_tokens + completion_tokens,
            **search_metrics
        }
    }

    if include_embeddings:
        response_data['query_embedding'] = search_result['query_embedding']

    return response_data


# ---------------------------------------------------------------------------
# Helpers exported for the SSE streaming path in api/server.py
# ---------------------------------------------------------------------------

def search_chunks(
    query: str,
    document_ids: Optional[List[str]],
    top_k: int,
    min_similarity: float,
    config: dict,
    conn=None,
    include_embeddings: bool = False,
):
    """Search for relevant chunks. Returns (chunks_list, query_embedding).

    This wrapper adapts the streaming-friendly signature expected by the SSE
    endpoint to the internal similarity-search implementation.  When ``conn``
    is provided it is passed through to avoid creating a new connection pool.
    """
    search_result = _search_chunks_internal(
        query, top_k, min_similarity, document_ids, config, conn=conn,
    )
    return search_result['results'], search_result['query_embedding']


def build_prompt(
    query: str,
    chunks: List[Dict[str, Any]],
    config: dict,
    session_context: str = "",
) -> List[Dict[str, str]]:
    """Build the LLM messages list from a query and retrieved chunks.

    Returns a messages list suitable for ``generate_response``.
    """
    context = "\n\n".join([f"From {c['document_id']}: {c['text']}" for c in chunks])
    system_content = "You are a helpful assistant. Use the following context to answer the user's question accurately. If the context doesn't contain relevant information, say so."
    user_content = f"Context:\n{context}"
    if session_context:
        user_content += f"\n\nConversation so far:\n{session_context}"
    user_content += f"\n\nQuestion: {query}"
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]
