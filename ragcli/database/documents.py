"""Document persistence operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class _Connection(Protocol):
    def cursor(self): ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def close(self) -> None: ...


class _DatabaseClient(Protocol):
    def get_connection(self) -> _Connection: ...


class DocumentNotFound(Exception):
    """Raised when a document id does not exist."""


@dataclass(frozen=True)
class DeletedDocument:
    document_id: str
    filename: str
    chunks_deleted: int


class DocumentRepository:
    """Repository for document rows and their dependent chunks."""

    def __init__(self, client: _DatabaseClient):
        self._client = client

    def delete_document(self, doc_id: str) -> DeletedDocument:
        conn = self._client.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT filename FROM DOCUMENTS WHERE document_id = :doc_id",
                    {"doc_id": doc_id},
                )
                result = cursor.fetchone()
                if not result:
                    raise DocumentNotFound(doc_id)

                filename = result[0]

                cursor.execute(
                    "DELETE FROM CHUNKS WHERE document_id = :doc_id",
                    {"doc_id": doc_id},
                )
                chunks_deleted = cursor.rowcount

                cursor.execute(
                    "DELETE FROM DOCUMENTS WHERE document_id = :doc_id",
                    {"doc_id": doc_id},
                )

            conn.commit()
            return DeletedDocument(
                document_id=doc_id,
                filename=filename,
                chunks_deleted=chunks_deleted,
            )
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
