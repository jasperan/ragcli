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
class DocumentRecord:
    document_id: str
    filename: str
    file_format: str
    file_size_bytes: int
    chunk_count: int
    total_tokens: int
    upload_timestamp: object
    last_modified: object


@dataclass(frozen=True)
class DocumentPage:
    documents: list[DocumentRecord]
    total_count: int


@dataclass(frozen=True)
class DeletedDocument:
    document_id: str
    filename: str
    chunks_deleted: int


class DocumentRepository:
    """Repository for document rows and their dependent chunks."""

    def __init__(self, client: _DatabaseClient):
        self._client = client

    def list_documents(self, *, limit: int, offset: int) -> DocumentPage:
        conn = self._client.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT document_id, filename, file_format, file_size_bytes,
                           chunk_count, total_tokens, upload_timestamp, last_modified
                    FROM DOCUMENTS
                    ORDER BY upload_timestamp DESC
                    OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
                    """,
                    {"offset": offset, "limit": limit},
                )
                rows = cursor.fetchall()

                cursor.execute("SELECT COUNT(*) FROM DOCUMENTS")
                total_count = cursor.fetchone()[0]

            return DocumentPage(
                documents=[
                    DocumentRecord(
                        document_id=row[0],
                        filename=row[1],
                        file_format=row[2],
                        file_size_bytes=row[3],
                        chunk_count=row[4],
                        total_tokens=row[5],
                        upload_timestamp=row[6],
                        last_modified=row[7],
                    )
                    for row in rows
                ],
                total_count=total_count,
            )
        finally:
            conn.close()

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
