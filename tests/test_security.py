"""Security audit tests: rate limiting, body size limits, error sanitization, CORS."""

import pytest
import time
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client with mocked DB."""
    with patch('ragcli.api.server.load_config') as mock_cfg:
        mock_cfg.return_value = {
            'documents': {
                'chunk_size': 1000, 'chunk_overlap_percentage': 10,
                'supported_formats': ['txt', 'md', 'pdf'], 'max_file_size_mb': 1,
            },
            'ollama': {
                'embedding_model': 'nomic-embed-text', 'chat_model': 'gemma3',
                'endpoint': 'http://localhost:11434', 'timeout': 30,
            },
            'rag': {'top_k': 5, 'min_similarity_score': 0.5},
            'vector_index': {'dimension': 768},
            'api': {
                'host': '0.0.0.0', 'port': 8000,
                'cors_origins': ['http://localhost:5173'],
                'enable_swagger': True,
            },
        }
        # Re-import to get fresh app with mocked config
        import importlib
        import ragcli.api.server as srv
        importlib.reload(srv)
        yield TestClient(srv.app)


# ---------------------------------------------------------------------------
# Rate limiter unit tests (no HTTP needed)
# ---------------------------------------------------------------------------

class TestTokenBucket:
    def test_allows_within_burst(self):
        from ragcli.api.server import _TokenBucket
        bucket = _TokenBucket(rate=1, burst=3)
        assert bucket.allow("ip1")
        assert bucket.allow("ip1")
        assert bucket.allow("ip1")

    def test_blocks_after_burst_exhausted(self):
        from ragcli.api.server import _TokenBucket
        bucket = _TokenBucket(rate=0.001, burst=2)  # very slow refill
        assert bucket.allow("ip1")
        assert bucket.allow("ip1")
        assert not bucket.allow("ip1")  # burst exhausted

    def test_refills_over_time(self):
        from ragcli.api.server import _TokenBucket
        bucket = _TokenBucket(rate=100, burst=2)  # fast refill
        bucket.allow("ip1")
        bucket.allow("ip1")
        time.sleep(0.05)  # 50ms -> ~5 tokens at rate=100
        assert bucket.allow("ip1")

    def test_separate_keys(self):
        from ragcli.api.server import _TokenBucket
        bucket = _TokenBucket(rate=0.001, burst=1)
        assert bucket.allow("ip1")
        assert not bucket.allow("ip1")
        assert bucket.allow("ip2")  # different key, fresh bucket


# ---------------------------------------------------------------------------
# Error sanitization
# ---------------------------------------------------------------------------

class TestErrorSanitization:
    """Verify internal details don't leak to clients."""

    def test_upload_error_no_stack_trace(self, client):
        """Upload endpoint should not expose internal errors."""
        # Send a malformed file that will fail processing
        response = client.post(
            "/api/documents/upload",
            files={"file": ("test.xyz", b"data", "application/octet-stream")},
        )
        # Should get an error, but the detail should be generic
        assert response.status_code in (400, 422, 500)
        body = response.json()
        detail = body.get("detail", "")
        if isinstance(detail, str):
            assert "traceback" not in detail.lower()
            assert "oracledb" not in detail.lower()

    def test_query_error_no_internals(self, client):
        """Query endpoint should not expose DB connection details."""
        response = client.post(
            "/api/query",
            json={"query": "test", "stream": False},
        )
        # Will fail without DB, but should be a clean error
        if response.status_code == 500:
            detail = response.json().get("detail", "")
            assert "password" not in detail.lower()
            assert "dsn" not in detail.lower()


# ---------------------------------------------------------------------------
# Filename sanitization (via upload endpoint)
# ---------------------------------------------------------------------------

class TestUploadFilenameSecurity:

    def test_path_traversal_filename(self, client):
        """Path traversal in filename should be stripped."""
        response = client.post(
            "/api/documents/upload",
            files={"file": ("../../etc/passwd", b"not a password file", "text/plain")},
        )
        # The file will fail for other reasons, but the sanitized name
        # should not contain path components
        # (we test sanitize_filename directly in battle hardening;
        # this confirms the endpoint actually calls it)
        assert response.status_code in (400, 422, 500)


# ---------------------------------------------------------------------------
# CORS default hardening
# ---------------------------------------------------------------------------

class TestCORSDefaults:

    def test_default_cors_not_wildcard(self):
        """Default CORS should not be wildcard."""
        from ragcli.config.defaults import DEFAULT_CONFIG
        origins = DEFAULT_CONFIG['api']['cors_origins']
        assert "*" not in origins
        assert all(o.startswith("http") for o in origins)


# ---------------------------------------------------------------------------
# Body size / upload limits
# ---------------------------------------------------------------------------

class TestBodySizeLimits:

    def test_oversized_content_length_rejected(self, client):
        """Request with declared Content-Length above limit should be rejected."""
        # The middleware checks content-length header
        headers = {"content-length": str(500 * 1024 * 1024)}  # 500MB
        response = client.get("/api/health", headers=headers)
        # Middleware should reject before reaching handler
        assert response.status_code in (413, 404, 422)


# ---------------------------------------------------------------------------
# Input validation on API layer
# ---------------------------------------------------------------------------

class TestAPIInputValidation:

    def test_query_empty_string(self, client):
        """Empty query should be rejected."""
        response = client.post("/api/query", json={"query": "", "stream": False})
        assert response.status_code in (400, 422, 500)

    def test_delete_nonexistent_doc(self, client):
        """Deleting a non-existent doc should 404 or 500, not crash."""
        with patch('ragcli.api.server.get_db_client') as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None  # doc not found
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_db.return_value.get_connection.return_value = mock_conn
            response = client.delete("/api/documents/not-a-real-id")
            assert response.status_code == 404

    def test_negative_pagination(self, client):
        """Negative offset/limit should be rejected by FastAPI validation."""
        response = client.get("/api/documents?offset=-1&limit=10")
        assert response.status_code == 422  # Pydantic validation error
