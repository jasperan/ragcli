"""Pydantic models for ragcli API."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class DocumentUploadResponse(BaseModel):
    """Response for document upload."""
    document_id: str
    filename: str
    file_format: str
    file_size_bytes: int
    chunk_count: int
    total_tokens: int
    upload_time_ms: float
    message: str = "Document uploaded successfully"


class DocumentInfo(BaseModel):
    """Document metadata."""
    document_id: str
    filename: str
    file_format: str
    file_size_bytes: int
    chunk_count: int
    total_tokens: int
    upload_timestamp: datetime
    last_modified: datetime


class DocumentListResponse(BaseModel):
    """Response for listing documents."""
    documents: List[DocumentInfo]
    total_count: int


class QueryRequest(BaseModel):
    """Request for RAG query."""
    query: str = Field(..., min_length=1, description="The question to ask")
    document_ids: Optional[List[str]] = Field(None, description="Filter by specific document IDs")
    top_k: Optional[int] = Field(5, ge=1, le=50, description="Number of chunks to retrieve")
    min_similarity: Optional[float] = Field(0.5, ge=0.0, le=1.0, description="Minimum similarity score")
    stream: bool = Field(False, description="Enable streaming response")


class ChunkResult(BaseModel):
    """Retrieved chunk information."""
    chunk_id: str
    document_id: str
    text: str
    similarity_score: float
    chunk_index: int


class QueryResponse(BaseModel):
    """Response for RAG query."""
    response: str
    chunks: List[ChunkResult]
    metrics: Dict[str, Any]


class OllamaModel(BaseModel):
    """Ollama model information."""
    name: str
    size: int
    modified_at: str
    family: Optional[str] = None
    parameter_size: Optional[str] = None


class ModelsResponse(BaseModel):
    """Response for listing models."""
    embedding_models: List[OllamaModel]
    chat_models: List[OllamaModel]
    current_embedding_model: str
    current_chat_model: str


class ComponentStatus(BaseModel):
    """Status of a system component."""
    status: str
    message: str


class SystemStatus(BaseModel):
    """Overall system status."""
    healthy: bool
    database: ComponentStatus
    ollama: ComponentStatus
    vllm: ComponentStatus
    timestamp: datetime


class SystemStats(BaseModel):
    """System statistics."""
    total_documents: int
    total_vectors: int
    total_tokens: int
    embedding_dimension: int
    index_type: Optional[str] = None

