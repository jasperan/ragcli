"""Performance tests: verify batch inserts, HTTP session reuse, connection pooling."""

import time
import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from ragcli.core.embedding import _get_http_session, generate_embedding
from ragcli.database.vector_ops import insert_chunks_batch


# ---------------------------------------------------------------------------
# HTTP Session reuse
# ---------------------------------------------------------------------------

class TestHTTPSessionReuse:

    def test_session_is_singleton(self):
        """Calling _get_http_session() twice returns the same object."""
        s1 = _get_http_session()
        s2 = _get_http_session()
        assert s1 is s2

    def test_session_has_connection_pooling(self):
        session = _get_http_session()
        adapter = session.get_adapter("http://localhost")
        # Should have pool_maxsize > 1
        assert adapter._pool_maxsize >= 10

    @patch('ragcli.core.embedding._get_http_session')
    def test_embedding_uses_session(self, mock_get_session):
        """generate_embedding should use the shared session, not raw requests.post."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": [0.1] * 768}
        mock_response.raise_for_status.return_value = None
        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_get_session.return_value = mock_session

        config = {
            'ollama': {'endpoint': 'http://localhost:11434', 'timeout': 30},
            'vector_index': {},
        }
        result = generate_embedding("test text", "nomic-embed-text", config)

        mock_session.post.assert_called_once()
        assert len(result) == 768


# ---------------------------------------------------------------------------
# Batch chunk inserts
# ---------------------------------------------------------------------------

class TestBatchInsert:

    def test_executemany_called(self):
        """insert_chunks_batch should use executemany for efficiency."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

        chunks = [
            {'text': f'chunk {i}', 'token_count': 5, 'char_count': 7,
             'embedding': [0.1] * 768, 'chunk_number': i}
            for i in range(10)
        ]

        ids = insert_chunks_batch(mock_conn, "doc-1", chunks, "nomic-embed-text")
        assert len(ids) == 10
        mock_cursor.executemany.assert_called_once()
        # executemany should receive 10 rows
        call_args = mock_cursor.executemany.call_args[0]
        assert len(call_args[1]) == 10

    def test_empty_batch(self):
        """Empty chunk list should not call executemany."""
        mock_conn = MagicMock()
        ids = insert_chunks_batch(mock_conn, "doc-1", [], "nomic-embed-text")
        assert ids == []

    def test_batch_vs_individual_overhead(self):
        """Benchmark: batch insert should be faster than N individual inserts."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

        n_chunks = 100
        chunks = [
            {'text': f'chunk {i}', 'token_count': 5, 'char_count': 7,
             'embedding': [0.1] * 768, 'chunk_number': i}
            for i in range(n_chunks)
        ]

        # Batch timing
        start = time.perf_counter()
        for _ in range(100):
            insert_chunks_batch(mock_conn, "doc-1", chunks, "model")
        batch_time = time.perf_counter() - start

        # Individual timing (simulated with same mock)
        from ragcli.database.vector_ops import insert_chunk
        start = time.perf_counter()
        for _ in range(100):
            for c in chunks:
                insert_chunk(mock_conn, "doc-1", c['chunk_number'], c['text'],
                             c['token_count'], c['char_count'],
                             embedding=c['embedding'], embedding_model="model")
        individual_time = time.perf_counter() - start

        # Batch should be faster (less Python overhead per row)
        print(f"\nBatch: {batch_time:.3f}s, Individual: {individual_time:.3f}s, "
              f"Speedup: {individual_time/batch_time:.1f}x")
        assert batch_time < individual_time


# ---------------------------------------------------------------------------
# Connection pool: single client per query (regression test)
# ---------------------------------------------------------------------------

class TestConnectionPooling:

    @patch('ragcli.core.rag_engine.OracleClient')
    @patch('ragcli.core.rag_engine.log_query')
    @patch('ragcli.core.rag_engine.generate_response')
    @patch('ragcli.core.rag_engine._search_chunks_internal')
    def test_query_creates_one_pool(self, mock_search, mock_gen, mock_log, mock_client):
        """Regression: ask_query must create exactly 1 OracleClient."""
        from ragcli.core.rag_engine import ask_query
        config = {
            'rag': {'top_k': 5, 'min_similarity_score': 0.5},
            'ollama': {'chat_model': 'test', 'embedding_model': 'test',
                       'endpoint': 'http://localhost:11434', 'timeout': 30},
        }
        mock_search.return_value = {
            'results': [{'document_id': 'd', 'text': 't', 'similarity_score': 0.9}],
            'query_embedding': [0.1]*768,
            'metrics': {'embedding_time_ms': 5, 'search_time_ms': 10},
        }
        mock_gen.return_value = "ok"
        mock_client.return_value.get_connection.return_value = MagicMock()

        ask_query("test", config=config)
        assert mock_client.call_count == 1, f"Expected 1 OracleClient, got {mock_client.call_count}"
