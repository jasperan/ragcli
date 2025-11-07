"""Main RAG orchestration for ragcli."""

import time
from typing import Dict, List, Any, Optional, Generator
from langchain_text_splitters import RecursiveCharacterTextSplitter
from .ocr_processor import pdf_to_markdown
from .embedding import generate_embedding, generate_response
from .similarity_search import search_chunks
from ..database.vector_ops import insert_document, insert_chunk
from ..database.oracle_client import OracleClient
from ..config.config_manager import load_config
from pathlib import Path

def upload_document(file_path: str, config: Optional[dict] = None) -> Dict[str, Any]:
    """Upload and process a document."""
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
    
    # Process text
    text = ""
    extracted_size = 0
    ocr_processed = 'N'
    
    if file_format == 'pdf':
        ocr_processed = 'Y'
        text = pdf_to_markdown(str(path), config) or ""
        extracted_size = len(text.encode('utf-8'))
    else:
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        extracted_size = len(text.encode('utf-8'))
    
    # Chunk
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config['documents']['chunk_size'],
        chunk_overlap=config['documents']['chunk_size'] * config['documents']['chunk_overlap_percentage'] // 100,
        length_function=len  # Simple char count, TODO: token count
    )
    chunks = splitter.split_text(text)
    
    # Simple token count: approx words
    total_tokens = sum(len(chunk.split()) for chunk in chunks)
    
    # Get client
    client = OracleClient(config)
    conn = client.get_connection()
    
    # Insert document
    doc_id = insert_document(
        conn, path.name, file_format.upper(), file_size, extracted_size,
        len(chunks), total_tokens, config['vector_index']['dimension'], ocr_processed
    )
    
    # Insert chunks with embeddings
    for i, chunk in enumerate(chunks):
        token_count = len(chunk.split())
        char_count = len(chunk)
        
        emb = generate_embedding(chunk, config['ollama']['embedding_model'], config)
        
        insert_chunk(
            conn, doc_id, i+1, chunk, token_count, char_count,
            embedding=emb, embedding_model=config['ollama']['embedding_model']
        )
    
    client.close()
    
    total_time = time.perf_counter() - start_time
    
    metadata = {
        'document_id': doc_id,
        'filename': path.name,
        'file_format': file_format,
        'file_size_bytes': file_size,
        'extracted_text_size_bytes': extracted_size,
        'chunk_count': len(chunks),
        'total_tokens': total_tokens,
        'embedding_dimension': config['vector_index']['dimension'],
        'approximate_embedding_size_bytes': len(chunks) * config['vector_index']['dimension'] * 4,
        'upload_time_ms': total_time * 1000,
        'ocr_processed': ocr_processed == 'Y'
    }
    
    return metadata

def ask_query(
    query: str,
    document_ids: Optional[List[str]] = None,
    top_k: Optional[int] = None,
    min_similarity: Optional[float] = None,
    config: Optional[dict] = None,
    stream: bool = False
) -> Dict[str, Any]:
    """Ask a query using RAG."""
    if config is None:
        config = load_config()
    
    top_k = top_k or config['rag']['top_k']
    min_similarity = min_similarity or config['rag']['min_similarity_score']
    
    start_time = time.perf_counter()
    
    # Search
    search_start = time.perf_counter()
    search_result = search_chunks(query, top_k, min_similarity, document_ids, config)
    search_time = time.perf_counter() - search_start
    
    results = search_result['results']
    
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
        # For now, collect to string for return
        response = "".join(response_generator)
    else:
        response = generate_response(messages, config['ollama']['chat_model'], config, stream=False)
    gen_time = time.perf_counter() - gen_start
    
    total_time = time.perf_counter() - start_time
    
    # Simple token estimate
    prompt_tokens = len(query.split()) + len(context.split())
    completion_tokens = len(response.split())
    
    return {
        'response': response,
        'results': results,
        'metrics': {
            'search_time_ms': search_time * 1000,
            'generation_time_ms': gen_time * 1000,
            'total_time_ms': total_time * 1000,
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': prompt_tokens + completion_tokens,
            **search_result['metrics']
        }
    }

# TODO: Log query to DB, reranking, advanced prompting, streaming full support
