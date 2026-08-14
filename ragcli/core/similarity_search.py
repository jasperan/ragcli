"""Similarity search orchestration for ragcli."""

import time
from typing import List, Dict, Any, Optional
from .embedding import generate_embedding
from ..database.oracle_client import OracleClient
from ..database.vector_ops import search_similar
from ..search.fusion import HybridSearch
from ..search.router import QueryRouter
from ..config.config_manager import load_config


def search_chunks(
    query: str,
    top_k: int,
    min_similarity: float,
    document_ids: Optional[List[str]] = None,
    config: dict = None,
    conn=None,
) -> Dict[str, Any]:
    """Perform search for query, return results with metrics.

    Honors the configured search strategy: ``vector_only`` runs the classic
    vector similarity path; ``hybrid`` (default) and ``bm25_only`` route
    through the RRF fusion engine (vector + BM25 + graph), applying the query
    router and per-chunk feedback quality scores when enabled.

    If ``conn`` is provided, it is used directly (caller manages lifecycle).
    Otherwise a temporary OracleClient + connection is created and closed.
    """
    if config is None:
        config = load_config()

    start_time = time.perf_counter()

    # Generate query embedding
    emb_start = time.perf_counter()
    query_embedding = generate_embedding(query, config['ollama']['embedding_model'], config)
    emb_time = time.perf_counter() - emb_start

    strategy = config.get('search', {}).get('strategy', 'hybrid')

    # Search — reuse caller's connection when available
    owns_conn = conn is None
    client = None
    if owns_conn:
        client = OracleClient(config)
        conn = client.get_connection()

    search_start = time.perf_counter()
    try:
        if strategy == 'vector_only':
            results = search_similar(conn, query_embedding, top_k, min_similarity, document_ids)
            signal_counts = {'vector': len(results), 'bm25': 0, 'graph': 0}
        else:
            hybrid = HybridSearch(conn, config)

            # Query router: decide which signals to activate per query
            signals = None
            if config.get('search', {}).get('use_router', True):
                signals = QueryRouter().route(query)

            fused = hybrid.search(
                query,
                top_k=top_k,
                document_ids=document_ids,
                signals=signals,
                min_similarity=min_similarity,
                query_embedding=query_embedding,
            )
            results = fused['results']
            signal_counts = fused['signal_counts']
    finally:
        if owns_conn:
            conn.close()
            if client:
                client.close()
    search_time = time.perf_counter() - search_start

    total_time = time.perf_counter() - start_time

    metrics = {
        'embedding_time_ms': emb_time * 1000,
        'search_time_ms': search_time * 1000,
        'total_time_ms': total_time * 1000,
        'num_results': len(results),
        'avg_similarity': sum(r['similarity_score'] for r in results) / len(results) if results else 0,
        'strategy': strategy,
        'signal_counts': signal_counts,
    }

    return {
        'results': results,
        'query_embedding': query_embedding,
        'metrics': metrics
    }
