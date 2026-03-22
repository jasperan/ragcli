"""Battle-hardening tests: edge cases, malformed inputs, failure modes, race conditions."""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from pathlib import Path

from ragcli.core.rag_engine import upload_document, ask_query, build_prompt, search_chunks
from ragcli.utils.validators import (
    validate_file_path, validate_query_text, validate_document_ids,
    validate_top_k, validate_similarity_threshold, sanitize_filename,
    ValidationError,
)
from ragcli.database.vector_ops import log_query, insert_document, insert_chunk


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def base_config():
    return {
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
    }


# ---------------------------------------------------------------------------
# Upload edge cases
# ---------------------------------------------------------------------------

class TestUploadEdgeCases:

    def test_upload_nonexistent_file(self, base_config):
        with pytest.raises(FileNotFoundError):
            upload_document("/no/such/file.txt", base_config)

    def test_upload_unsupported_format(self, base_config, tmp_path):
        f = tmp_path / "data.xlsx"
        f.write_text("spreadsheet")
        with pytest.raises(ValueError, match="Unsupported format"):
            upload_document(str(f), base_config)

    def test_upload_empty_file(self, base_config, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("")
        # Should proceed (empty text is valid, chunking produces 0 chunks)
        with patch('ragcli.core.rag_engine.OracleClient') as mc, \
             patch('ragcli.core.rag_engine.find_document_by_hash', return_value=None), \
             patch('ragcli.core.rag_engine.preprocess_document') as mp, \
             patch('ragcli.core.rag_engine.chunk_text') as mct, \
             patch('ragcli.core.rag_engine.get_document_metadata') as mm, \
             patch('ragcli.core.rag_engine.insert_document') as mid, \
             patch('ragcli.core.rag_engine.insert_chunks_batch', return_value=[]):
            mc.return_value.get_connection.return_value = MagicMock()
            mp.return_value = ("", False)
            mct.return_value = []
            mm.return_value = {'chunk_count': 0, 'total_tokens': 0, 'extracted_text_size_bytes': 0}
            mid.return_value = "empty-doc-id"
            result = upload_document(str(f), base_config)
            assert result['chunk_count'] == 0

    def test_upload_file_too_large(self, base_config, tmp_path):
        f = tmp_path / "big.txt"
        # Config says max 1MB
        f.write_bytes(b"x" * (2 * 1024 * 1024))
        with pytest.raises(ValueError, match="File too large"):
            upload_document(str(f), base_config)

    def test_upload_rollback_on_db_error(self, base_config, tmp_path):
        f = tmp_path / "ok.txt"
        f.write_text("some content")
        mock_conn = MagicMock()
        with patch('ragcli.core.rag_engine.OracleClient') as mc, \
             patch('ragcli.core.rag_engine.find_document_by_hash', return_value=None), \
             patch('ragcli.core.rag_engine.preprocess_document') as mp, \
             patch('ragcli.core.rag_engine.chunk_text') as mct, \
             patch('ragcli.core.rag_engine.get_document_metadata') as mm, \
             patch('ragcli.core.rag_engine.insert_document') as mid:
            mc.return_value.get_connection.return_value = mock_conn
            mp.return_value = ("text", False)
            mct.return_value = [{'text': 'chunk', 'token_count': 1, 'char_count': 5}]
            mm.return_value = {'chunk_count': 1, 'total_tokens': 1, 'extracted_text_size_bytes': 4}
            mid.side_effect = Exception("DB insert failed")
            with pytest.raises(Exception, match="DB insert failed"):
                upload_document(str(f), base_config)
            mock_conn.rollback.assert_called_once()
            mock_conn.close.assert_called_once()


# ---------------------------------------------------------------------------
# Query edge cases
# ---------------------------------------------------------------------------

class TestQueryEdgeCases:

    @patch('ragcli.core.rag_engine.OracleClient')
    @patch('ragcli.core.rag_engine.log_query')
    @patch('ragcli.core.rag_engine.generate_response')
    @patch('ragcli.core.rag_engine._search_chunks_internal')
    def test_query_no_results(self, mock_search, mock_gen, mock_log, mock_client, base_config):
        """Query that returns zero matching chunks."""
        mock_search.return_value = {
            'results': [],
            'query_embedding': [0.0] * 768,
            'metrics': {'embedding_time_ms': 5, 'search_time_ms': 10},
        }
        mock_gen.return_value = "No relevant context found."
        mock_client.return_value.get_connection.return_value = MagicMock()

        result = ask_query("obscure question nobody asked", config=base_config)
        assert result['response'] == "No relevant context found."
        assert len(result['results']) == 0

    @patch('ragcli.core.rag_engine.OracleClient')
    @patch('ragcli.core.rag_engine.log_query')
    @patch('ragcli.core.rag_engine.generate_response')
    @patch('ragcli.core.rag_engine._search_chunks_internal')
    def test_query_single_client_used(self, mock_search, mock_gen, mock_log, mock_client, base_config):
        """Verify only ONE OracleClient is created per query (fix for connection pool leak)."""
        mock_search.return_value = {
            'results': [{'document_id': 'd1', 'text': 'chunk', 'similarity_score': 0.9}],
            'query_embedding': [0.1] * 768,
            'metrics': {'embedding_time_ms': 5, 'search_time_ms': 10},
        }
        mock_gen.return_value = "answer"
        mock_client.return_value.get_connection.return_value = MagicMock()

        ask_query("test", config=base_config)
        # Should be called exactly once (was 3 before the fix)
        assert mock_client.call_count == 1

    @patch('ragcli.core.rag_engine.OracleClient')
    @patch('ragcli.core.rag_engine.log_query')
    @patch('ragcli.core.rag_engine.generate_response')
    @patch('ragcli.core.rag_engine._search_chunks_internal')
    def test_query_with_session_single_client(self, mock_search, mock_gen, mock_log, mock_client, base_config):
        """Even with session_id, only one OracleClient should be created."""
        mock_search.return_value = {
            'results': [{'document_id': 'd1', 'text': 'c', 'similarity_score': 0.8, 'chunk_id': 'ch1'}],
            'query_embedding': [0.1] * 768,
            'metrics': {'embedding_time_ms': 5, 'search_time_ms': 10},
        }
        mock_gen.return_value = "answer"
        mock_conn = MagicMock()
        mock_client.return_value.get_connection.return_value = mock_conn

        with patch('ragcli.core.rag_engine.SessionManager') as mock_sm, \
             patch('ragcli.core.rag_engine.ContextManager') as mock_cm:
            mock_sm.return_value.get_recent_turns.return_value = []
            mock_sm.return_value.get_summary.return_value = None
            mock_sm.return_value.get_turn_count.return_value = 0
            mock_cm.return_value.should_summarize.return_value = False

            base_config['memory'] = {'max_recent_turns': 5, 'summarize_every': 5}
            ask_query("test", config=base_config, session_id="sess-123")
            assert mock_client.call_count == 1

    @patch('ragcli.core.rag_engine.OracleClient')
    @patch('ragcli.core.rag_engine.log_query')
    @patch('ragcli.core.rag_engine.generate_response')
    @patch('ragcli.core.rag_engine._search_chunks_internal')
    def test_query_total_time_in_metrics(self, mock_search, mock_gen, mock_log, mock_client, base_config):
        """Verify total_time_ms is populated in the response metrics."""
        mock_search.return_value = {
            'results': [{'document_id': 'd1', 'text': 'c', 'similarity_score': 0.8}],
            'query_embedding': [0.1] * 768,
            'metrics': {'embedding_time_ms': 5, 'search_time_ms': 10},
        }
        mock_gen.return_value = "answer"
        mock_client.return_value.get_connection.return_value = MagicMock()

        result = ask_query("test", config=base_config)
        assert 'total_time_ms' in result['metrics']
        assert result['metrics']['total_time_ms'] > 0

    @patch('ragcli.core.rag_engine.OracleClient')
    @patch('ragcli.core.rag_engine.log_query')
    @patch('ragcli.core.rag_engine.generate_response')
    @patch('ragcli.core.rag_engine._search_chunks_internal')
    def test_query_total_time_passed_to_log(self, mock_search, mock_gen, mock_log, mock_client, base_config):
        """Verify total_time_ms is passed through to log_query timing dict."""
        mock_search.return_value = {
            'results': [], 'query_embedding': [0.1] * 768,
            'metrics': {'embedding_time_ms': 5, 'search_time_ms': 10},
        }
        mock_gen.return_value = "a"
        mock_client.return_value.get_connection.return_value = MagicMock()

        ask_query("test", config=base_config)
        mock_log.assert_called_once()
        # log_query(conn, query, emb, doc_ids, top_k, min_sim, results, response, tokens, timing)
        # timing is the last positional arg
        all_args = mock_log.call_args[0]
        timing = all_args[-1]  # last positional arg
        assert 'total_time_ms' in timing
        assert timing['total_time_ms'] > 0


# ---------------------------------------------------------------------------
# Validator edge cases
# ---------------------------------------------------------------------------

class TestValidatorEdgeCases:

    def test_query_xss_script_tag(self):
        with pytest.raises(ValidationError, match="harmful"):
            validate_query_text('<script>alert("xss")</script>')

    def test_query_javascript_uri(self):
        with pytest.raises(ValidationError, match="harmful"):
            validate_query_text('javascript:void(0)')

    def test_query_vbscript_uri(self):
        with pytest.raises(ValidationError, match="harmful"):
            validate_query_text('vbscript:something')

    def test_query_whitespace_only(self):
        with pytest.raises(ValidationError):
            validate_query_text("   \t\n  ")

    def test_query_very_long(self):
        long_query = "a" * 20000
        with pytest.raises(ValidationError, match="too long"):
            validate_query_text(long_query)

    def test_query_non_string(self):
        with pytest.raises(ValidationError, match="must be a string"):
            validate_query_text(12345)

    def test_doc_ids_non_uuid(self):
        with pytest.raises(ValidationError, match="Invalid document ID"):
            validate_document_ids(["not-a-uuid"])

    def test_doc_ids_dedup(self):
        uid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        result = validate_document_ids([uid, uid, uid])
        assert len(result) == 1

    def test_doc_ids_too_many(self):
        uids = [f"aaaaaaaa-bbbb-cccc-dddd-{i:012d}" for i in range(60)]
        with pytest.raises(ValidationError, match="Too many"):
            validate_document_ids(uids)

    def test_top_k_zero(self):
        with pytest.raises(ValidationError, match="too small"):
            validate_top_k(0)

    def test_top_k_huge(self):
        with pytest.raises(ValidationError, match="too large"):
            validate_top_k(999)

    def test_similarity_out_of_range(self):
        with pytest.raises(ValidationError):
            validate_similarity_threshold(1.5)

    def test_similarity_negative(self):
        with pytest.raises(ValidationError):
            validate_similarity_threshold(-0.1)


# ---------------------------------------------------------------------------
# Filename sanitization
# ---------------------------------------------------------------------------

class TestSanitizeFilename:

    def test_path_traversal(self):
        result = sanitize_filename("../../etc/passwd")
        assert "/" not in result
        assert "\\" not in result
        assert result == "passwd"

    def test_null_bytes(self):
        result = sanitize_filename("file\x00.txt")
        assert "\x00" not in result

    def test_very_long_name(self):
        result = sanitize_filename("a" * 500 + ".pdf")
        assert len(result) <= 255

    def test_empty_string(self):
        result = sanitize_filename("")
        assert result == "upload"

    def test_only_dots(self):
        result = sanitize_filename("...")
        assert result == "upload"  # all dots stripped -> fallback

    def test_windows_reserved(self):
        # Should strip or rename Windows-reserved device names
        result = sanitize_filename("CON.txt")
        assert result != ""

    def test_slash_in_name(self):
        result = sanitize_filename("path/to/file.txt")
        assert "/" not in result


# ---------------------------------------------------------------------------
# log_query total_time_ms fix verification
# ---------------------------------------------------------------------------

class TestLogQueryTotalTime:

    def test_total_time_explicit(self):
        """When total_time_ms is explicitly provided, it should be used."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

        log_query(
            mock_conn, "test", [0.1]*10, None, 5, 0.5,
            [], "response", 1,
            {'embedding_time_ms': 10, 'search_time_ms': 20, 'generation_time_ms': 30, 'total_time_ms': 100}
        )

        # Check the execute call has total_time_ms = 100
        call_args = mock_cursor.execute.call_args_list[0]
        bind_dict = call_args[0][1]
        assert bind_dict['v_total_time'] == 100

    def test_total_time_computed_when_missing(self):
        """When total_time_ms is not provided, it should sum the components."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

        log_query(
            mock_conn, "test", [0.1]*10, None, 5, 0.5,
            [], "response", 1,
            {'embedding_time_ms': 10, 'search_time_ms': 20, 'generation_time_ms': 30}
        )

        call_args = mock_cursor.execute.call_args_list[0]
        bind_dict = call_args[0][1]
        assert bind_dict['v_total_time'] == 60  # 10 + 20 + 30


# ---------------------------------------------------------------------------
# build_prompt edge cases
# ---------------------------------------------------------------------------

class TestBuildPrompt:

    def test_empty_chunks(self, base_config):
        messages = build_prompt("question?", [], base_config)
        assert len(messages) == 2
        assert "question?" in messages[1]['content']

    def test_session_context_included(self, base_config):
        messages = build_prompt("follow-up", [], base_config, session_context="prev Q&A")
        assert "prev Q&A" in messages[1]['content']

    def test_large_context_assembly(self, base_config):
        chunks = [{'document_id': f'd{i}', 'text': f'chunk {i} ' * 100} for i in range(20)]
        messages = build_prompt("q", chunks, base_config)
        assert len(messages[1]['content']) > 1000


# ---------------------------------------------------------------------------
# Connection cleanup verification
# ---------------------------------------------------------------------------

class TestConnectionCleanup:

    @patch('ragcli.core.rag_engine.OracleClient')
    @patch('ragcli.core.rag_engine.log_query')
    @patch('ragcli.core.rag_engine.generate_response')
    @patch('ragcli.core.rag_engine._search_chunks_internal')
    def test_client_closed_on_success(self, mock_search, mock_gen, mock_log, mock_client, base_config):
        mock_search.return_value = {
            'results': [], 'query_embedding': [0.1]*768,
            'metrics': {'embedding_time_ms': 5, 'search_time_ms': 10},
        }
        mock_gen.return_value = "ok"
        mock_client.return_value.get_connection.return_value = MagicMock()

        ask_query("test", config=base_config)
        mock_client.return_value.close.assert_called_once()

    @patch('ragcli.core.rag_engine.OracleClient')
    @patch('ragcli.core.rag_engine.generate_response')
    @patch('ragcli.core.rag_engine._search_chunks_internal')
    def test_client_closed_on_error(self, mock_search, mock_gen, mock_client, base_config):
        mock_search.side_effect = Exception("search boom")
        mock_client.return_value.get_connection.return_value = MagicMock()

        with pytest.raises(Exception, match="search boom"):
            ask_query("test", config=base_config)
        mock_client.return_value.close.assert_called_once()

    def test_upload_client_closed_on_error(self, base_config, tmp_path):
        f = tmp_path / "ok.txt"
        f.write_text("content")
        with patch('ragcli.core.rag_engine.OracleClient') as mc, \
             patch('ragcli.core.rag_engine.preprocess_document') as mp:
            mp.side_effect = Exception("preprocess boom")
            mc.return_value.get_connection.return_value = MagicMock()
            with pytest.raises(Exception, match="preprocess boom"):
                upload_document(str(f), base_config)
            mc.return_value.close.assert_called_once()


# ---------------------------------------------------------------------------
# search_chunks wrapper
# ---------------------------------------------------------------------------

class TestSearchChunksWrapper:

    @patch('ragcli.core.rag_engine._search_chunks_internal')
    def test_returns_tuple(self, mock_internal, base_config):
        mock_internal.return_value = {
            'results': [{'chunk_id': 'c1', 'text': 'hi'}],
            'query_embedding': [0.5]*768,
            'metrics': {},
        }
        chunks, embedding = search_chunks("q", None, 5, 0.5, base_config)
        assert len(chunks) == 1
        assert len(embedding) == 768

    @patch('ragcli.core.rag_engine._search_chunks_internal')
    def test_conn_param_ignored(self, mock_internal, base_config):
        """The conn parameter should be accepted but ignored."""
        mock_internal.return_value = {
            'results': [], 'query_embedding': [0.1]*768, 'metrics': {},
        }
        # Should not raise even with a garbage conn
        chunks, emb = search_chunks("q", None, 5, 0.5, base_config, conn="garbage")
        assert chunks == []
