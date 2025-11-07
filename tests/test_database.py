"""Tests for ragcli database integration."""

import pytest
from unittest.mock import Mock, patch
from ragcli.database.oracle_client import OracleClient
from ragcli.config.config_manager import load_config

def test_oracle_client_init():
    """Test OracleClient initialization with mock config."""
    config = load_config("config.yaml.example")
    with patch('oracledb.create_pool') as mock_pool:
        client = OracleClient(config)
        mock_pool.assert_called_once()
        assert client.pool is not None

def test_init_db_success():
    """Test init_db with mock connection."""
    config = load_config("config.yaml.example")
    with patch('ragcli.database.oracle_client.OracleClient.get_connection') as mock_get:
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get.return_value = mock_conn
        
        from ragcli.database.schemas import get_create_schemas_sql
        sqls = get_create_schemas_sql()
        mock_cursor.execute.side_effect = [None] * len(sqls)
        
        client = OracleClient(config)
        client.init_db()
        
        assert mock_conn.commit.called
        assert mock_cursor.execute.call_count == len(sqls)

# TODO: Add more tests for vector_ops, error cases, retries
