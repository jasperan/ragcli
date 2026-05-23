from unittest.mock import MagicMock

import pytest

from ragcli.database.documents import DocumentNotFound, DocumentRepository


def _repository_with_cursor(cursor):
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    conn.cursor.return_value.__exit__.return_value = False
    client = MagicMock()
    client.get_connection.return_value = conn
    return DocumentRepository(client), conn


def test_list_documents_returns_page_and_closes_connection():
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        ("doc-1", "guide.pdf", "pdf", 1024, 3, 450, "2026-05-23T00:00:00", "2026-05-23T00:00:00"),
        ("doc-2", "notes.md", "md", 512, 1, 120, "2026-05-22T00:00:00", "2026-05-22T00:00:00"),
    ]
    cursor.fetchone.return_value = (12,)
    repo, conn = _repository_with_cursor(cursor)

    page = repo.list_documents(limit=2, offset=10)

    assert page.total_count == 12
    assert [document.document_id for document in page.documents] == ["doc-1", "doc-2"]
    assert page.documents[0].filename == "guide.pdf"
    assert cursor.execute.call_args_list[0].args[1] == {"offset": 10, "limit": 2}
    assert cursor.execute.call_args_list[1].args[0] == "SELECT COUNT(*) FROM DOCUMENTS"
    conn.close.assert_called_once()


def test_list_documents_closes_connection_on_error():
    cursor = MagicMock()
    cursor.execute.side_effect = RuntimeError("query failed")
    repo, conn = _repository_with_cursor(cursor)

    with pytest.raises(RuntimeError, match="query failed"):
        repo.list_documents(limit=100, offset=0)

    conn.close.assert_called_once()
    conn.commit.assert_not_called()
    conn.rollback.assert_not_called()


def test_delete_document_raises_not_found():
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    repo, conn = _repository_with_cursor(cursor)

    with pytest.raises(DocumentNotFound):
        repo.delete_document("missing-doc")

    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()
    conn.close.assert_called_once()


def test_delete_document_deletes_chunks_then_document_and_commits():
    cursor = MagicMock()
    cursor.fetchone.return_value = ("guide.pdf",)
    cursor.rowcount = 7
    repo, conn = _repository_with_cursor(cursor)

    deleted = repo.delete_document("doc-123")

    assert deleted.document_id == "doc-123"
    assert deleted.filename == "guide.pdf"
    assert deleted.chunks_deleted == 7
    assert cursor.execute.call_args_list[0].args[0] == (
        "SELECT filename FROM DOCUMENTS WHERE document_id = :doc_id"
    )
    assert cursor.execute.call_args_list[1].args[0] == (
        "DELETE FROM CHUNKS WHERE document_id = :doc_id"
    )
    assert cursor.execute.call_args_list[2].args[0] == (
        "DELETE FROM DOCUMENTS WHERE document_id = :doc_id"
    )
    conn.commit.assert_called_once()
    conn.rollback.assert_not_called()
    conn.close.assert_called_once()


def test_delete_document_rolls_back_on_delete_error():
    cursor = MagicMock()
    cursor.fetchone.return_value = ("guide.pdf",)
    cursor.execute.side_effect = [None, RuntimeError("delete failed")]
    repo, conn = _repository_with_cursor(cursor)

    with pytest.raises(RuntimeError, match="delete failed"):
        repo.delete_document("doc-123")

    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()
    conn.close.assert_called_once()
