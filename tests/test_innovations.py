"""Tests for Phase 7 innovations: embedding cache, health endpoint, document dedup."""

import pytest
import time
from unittest.mock import patch, MagicMock, Mock

from ragcli.core.embedding import EmbeddingCache, get_embedding_cache, generate_embedding


# ---------------------------------------------------------------------------
# Innovation 1: Embedding cache
# ---------------------------------------------------------------------------

class TestEmbeddingCache:

    def test_cache_miss_then_hit(self):
        cache = EmbeddingCache(max_size=10)
        assert cache.get("hello", "model-a") is None
        cache.put("hello", "model-a", [0.1, 0.2])
        assert cache.get("hello", "model-a") == [0.1, 0.2]

    def test_different_models_separate_keys(self):
        cache = EmbeddingCache(max_size=10)
        cache.put("hello", "model-a", [1.0])
        cache.put("hello", "model-b", [2.0])
        assert cache.get("hello", "model-a") == [1.0]
        assert cache.get("hello", "model-b") == [2.0]

    def test_lru_eviction(self):
        cache = EmbeddingCache(max_size=3)
        cache.put("a", "m", [1.0])
        cache.put("b", "m", [2.0])
        cache.put("c", "m", [3.0])
        cache.put("d", "m", [4.0])  # evicts "a"
        assert cache.get("a", "m") is None
        assert cache.get("b", "m") == [2.0]

    def test_lru_access_refreshes(self):
        cache = EmbeddingCache(max_size=3)
        cache.put("a", "m", [1.0])
        cache.put("b", "m", [2.0])
        cache.put("c", "m", [3.0])
        cache.get("a", "m")  # refresh "a"
        cache.put("d", "m", [4.0])  # evicts "b" (oldest untouched)
        assert cache.get("a", "m") == [1.0]
        assert cache.get("b", "m") is None

    def test_hit_rate_tracking(self):
        cache = EmbeddingCache(max_size=10)
        cache.put("x", "m", [1.0])
        cache.get("x", "m")  # hit
        cache.get("y", "m")  # miss
        assert cache.hits == 1
        assert cache.misses == 1
        assert cache.hit_rate == 0.5

    def test_stats(self):
        cache = EmbeddingCache(max_size=100)
        cache.put("a", "m", [1.0])
        s = cache.stats()
        assert s["size"] == 1
        assert s["max_size"] == 100

    def test_global_cache_singleton(self):
        c1 = get_embedding_cache()
        c2 = get_embedding_cache()
        assert c1 is c2

    @patch('ragcli.core.embedding._get_http_session')
    def test_cache_skips_api_call_on_hit(self, mock_session):
        """Second call for same text should not hit the API."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"embedding": [0.5] * 10}
        mock_resp.raise_for_status.return_value = None
        mock_session.return_value.post.return_value = mock_resp

        config = {'ollama': {'endpoint': 'http://localhost:11434', 'timeout': 30}, 'vector_index': {}}

        # Clear cache state
        cache = get_embedding_cache()
        old_hits = cache.hits

        r1 = generate_embedding("cached text", "model-x", config)
        r2 = generate_embedding("cached text", "model-x", config)

        assert r1 == r2
        # Only one API call should have been made
        assert mock_session.return_value.post.call_count == 1
        assert cache.hits >= old_hits + 1


# ---------------------------------------------------------------------------
# Innovation 2: Health endpoint
# ---------------------------------------------------------------------------

class TestHealthEndpoint:

    @pytest.fixture
    def client(self):
        with patch('ragcli.api.server.load_config') as mock_cfg:
            mock_cfg.return_value = {
                'documents': {'chunk_size': 1000, 'chunk_overlap_percentage': 10,
                              'supported_formats': ['txt'], 'max_file_size_mb': 1},
                'ollama': {'embedding_model': 'test', 'chat_model': 'test',
                           'endpoint': 'http://localhost:11434', 'timeout': 30},
                'rag': {'top_k': 5, 'min_similarity_score': 0.5},
                'vector_index': {'dimension': 768},
                'api': {'host': '0.0.0.0', 'port': 8000,
                        'cors_origins': ['http://localhost:5173'], 'enable_swagger': True},
            }
            import importlib
            import ragcli.api.server as srv
            importlib.reload(srv)
            from fastapi.testclient import TestClient
            yield TestClient(srv.app)

    def test_health_returns_structure(self, client):
        """Health endpoint should return checks structure."""
        with patch('ragcli.api.server.get_db_client') as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (1,)
            mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
            mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
            mock_db.return_value.get_connection.return_value = mock_conn

            with patch('ragcli.core.embedding._get_http_session') as mock_http:
                mock_resp = MagicMock()
                mock_resp.json.return_value = {"models": [{"name": "test"}]}
                mock_resp.raise_for_status.return_value = None
                mock_http.return_value.get.return_value = mock_resp

                resp = client.get("/api/health")
                assert resp.status_code == 200
                data = resp.json()
                assert data["healthy"] is True
                assert "database" in data["checks"]
                assert "ollama" in data["checks"]
                assert "embedding_cache" in data["checks"]
                assert data["checks"]["database"]["status"] == "ok"
                assert data["checks"]["ollama"]["status"] == "ok"


# ---------------------------------------------------------------------------
# Innovation 3: Document deduplication
# ---------------------------------------------------------------------------

class TestDocumentDedup:

    @patch('ragcli.core.rag_engine.OracleClient')
    @patch('ragcli.core.rag_engine.find_document_by_hash')
    @patch('ragcli.core.rag_engine.preprocess_document')
    def test_duplicate_detected(self, mock_preprocess, mock_find, mock_client, tmp_path):
        """Uploading duplicate content should return existing doc_id."""
        f = tmp_path / "dup.txt"
        f.write_text("same content")

        config = {
            'documents': {'chunk_size': 1000, 'chunk_overlap_percentage': 10,
                          'supported_formats': ['txt'], 'max_file_size_mb': 100},
            'ollama': {'embedding_model': 'test'},
            'vector_index': {'dimension': 768},
        }

        mock_client.return_value.get_connection.return_value = MagicMock()
        mock_preprocess.return_value = ("same content", False)
        mock_find.return_value = "existing-doc-id"

        from ragcli.core.rag_engine import upload_document
        result = upload_document(str(f), config)

        assert result['duplicate'] is True
        assert result['duplicate_of'] == "existing-doc-id"
        assert result['document_id'] == "existing-doc-id"

    @patch('ragcli.core.rag_engine.OracleClient')
    @patch('ragcli.core.rag_engine.find_document_by_hash')
    @patch('ragcli.core.rag_engine.insert_chunks_batch')
    @patch('ragcli.core.rag_engine.insert_document')
    @patch('ragcli.core.rag_engine.get_document_metadata')
    @patch('ragcli.core.rag_engine.chunk_text')
    @patch('ragcli.core.rag_engine.preprocess_document')
    @patch('ragcli.core.rag_engine.generate_embedding')
    def test_new_doc_proceeds(self, mock_emb, mock_preprocess, mock_chunk, mock_meta,
                               mock_insert_doc, mock_insert_batch, mock_find, mock_client, tmp_path):
        """Non-duplicate should proceed normally."""
        f = tmp_path / "new.txt"
        f.write_text("new content")

        config = {
            'documents': {'chunk_size': 1000, 'chunk_overlap_percentage': 10,
                          'supported_formats': ['txt'], 'max_file_size_mb': 100},
            'ollama': {'embedding_model': 'test'},
            'vector_index': {'dimension': 768},
        }

        mock_client.return_value.get_connection.return_value = MagicMock()
        mock_preprocess.return_value = ("new content", False)
        mock_find.return_value = None  # no duplicate
        mock_chunk.return_value = [{'text': 'new content', 'token_count': 2, 'char_count': 11}]
        mock_meta.return_value = {'chunk_count': 1, 'total_tokens': 2, 'extracted_text_size_bytes': 11}
        mock_insert_doc.return_value = "new-doc-id"
        mock_insert_batch.return_value = ["chunk-1"]
        mock_emb.return_value = [0.1] * 768

        from ragcli.core.rag_engine import upload_document
        result = upload_document(str(f), config)

        assert result.get('duplicate') is not True
        assert result['document_id'] == "new-doc-id"
        mock_insert_doc.assert_called_once()
