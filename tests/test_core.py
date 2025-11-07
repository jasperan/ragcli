"""Tests for ragcli core modules."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from ragcli.core.rag_engine import upload_document, ask_query
from ragcli.core.embedding import generate_embedding
from ragcli.core.similarity_search import search_chunks
from ragcli.database.vector_ops import insert_document, insert_chunk
from ragcli.database.oracle_client import OracleClient
from ragcli.core.ocr_processor import pdf_to_markdown

@patch('ragcli.core.rag_engine.load_config')
@patch('ragcli.core.rag_engine.pdf_to_markdown')
@patch('ragcli.core.rag_engine.insert_document')
@patch('ragcli.core.rag_engine.insert_chunk')
@patch('ragcli.core.rag_engine.generate_embedding')
def test_upload_document(mock_emb, mock_insert_chunk, mock_insert_doc, mock_ocr, mock_config):
    """Test document upload with mocks."""
    mock_config.return_value = {
        'documents': {'chunk_size': 1000, 'chunk_overlap_percentage': 10, 'supported_formats': ['txt']},
        'ollama': {'embedding_model': 'test'},
        'vector_index': {'dimension': 768}
    }
    mock_ocr.return_value = None  # For non-PDF
    mock_emb.return_value = [0.1] * 768
    
    with patch('builtins.open', Mock()) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = "Test text"
        
        metadata = upload_document('test.txt')
    
    mock_insert_doc.assert_called_once()
    mock_insert_chunk.assert_called()  # At least once for chunks
    assert metadata['chunk_count'] > 0

@patch('ragcli.core.rag_engine.load_config')
@patch('ragcli.core.rag_engine.search_chunks')
@patch('ragcli.core.rag_engine.generate_response')
def test_ask_query(mock_gen, mock_search, mock_config):
    """Test query asking with mocks."""
    mock_config.return_value = {'rag': {'top_k': 5}, 'ollama': {'chat_model': 'test'}}
    mock_search.return_value = {
        'results': [{'document_id': 'doc1', 'text': 'sample', 'similarity_score': 0.8}],
        'metrics': {'embedding_time_ms': 10, 'search_time_ms': 20}
    }
    mock_gen.return_value = "Sample answer"
    
    result = ask_query("test query")
    
    assert result['response'] == "Sample answer"
    assert 'metrics' in result
    assert len(result['results']) == 1

# TODO: More comprehensive tests, integration with real APIs (mocked), error cases
