"""FastAPI server for ragcli - AnythingLLM integration."""

import os
import tempfile
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn

from ragcli.config.config_manager import load_config
from ragcli.core.rag_engine import upload_document, ask_query
from ragcli.core.ollama_manager import (
    list_available_models,
    get_model_info,
    validate_model
)
from ragcli.database.oracle_client import OracleClient
from ragcli.utils.status import get_overall_status, get_document_stats
from .models import (
    DocumentUploadResponse,
    DocumentInfo,
    DocumentListResponse,
    QueryRequest,
    QueryResponse,
    ChunkResult,
    ModelsResponse,
    OllamaModel,
    SystemStatus,
    SystemStats,
    ComponentStatus
)

# Load config
config = load_config()

# Create FastAPI app
app = FastAPI(
    title="ragcli API",
    description="REST API for RAG operations with Oracle 26ai and Ollama",
    version="1.0.0",
    docs_url="/docs" if config.get('api', {}).get('enable_swagger', True) else None
)

# CORS middleware
cors_origins = config.get('api', {}).get('cors_origins', ["*"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "ragcli API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running"
    }


@app.post("/api/documents/upload", response_model=DocumentUploadResponse)
async def upload_document_endpoint(file: UploadFile = File(...)):
    """
    Upload and process a document.
    
    Supported formats: TXT, MD, PDF
    """
    try:
        # Save uploaded file to temp location
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        # Process document
        try:
            result = upload_document(tmp_path, config)
            
            return DocumentUploadResponse(
                document_id=result['document_id'],
                filename=result['filename'],
                file_format=result['file_format'],
                file_size_bytes=result['file_size_bytes'],
                chunk_count=result['chunk_count'],
                total_tokens=result['total_tokens'],
                upload_time_ms=result['upload_time_ms']
            )
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/api/documents", response_model=DocumentListResponse)
async def list_documents(
    limit: Optional[int] = Query(100, ge=1, le=1000),
    offset: Optional[int] = Query(0, ge=0)
):
    """List all documents with metadata."""
    try:
        client = OracleClient(config)
        conn = client.get_connection()
        cursor = conn.cursor()
        
        # Get documents with pagination
        cursor.execute("""
            SELECT document_id, filename, file_format, file_size_bytes, 
                   chunk_count, total_tokens, upload_timestamp, last_modified
            FROM DOCUMENTS
            ORDER BY upload_timestamp DESC
            OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
        """, {"offset": offset, "limit": limit})
        
        rows = cursor.fetchall()
        
        # Get total count
        cursor.execute("SELECT COUNT(*) FROM DOCUMENTS")
        total_count = cursor.fetchone()[0]
        
        client.close()
        
        documents = [
            DocumentInfo(
                document_id=row[0],
                filename=row[1],
                file_format=row[2],
                file_size_bytes=row[3],
                chunk_count=row[4],
                total_tokens=row[5],
                upload_timestamp=row[6],
                last_modified=row[7]
            )
            for row in rows
        ]
        
        return DocumentListResponse(
            documents=documents,
            total_count=total_count
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")


@app.delete("/api/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a document and all its chunks."""
    try:
        client = OracleClient(config)
        conn = client.get_connection()
        cursor = conn.cursor()
        
        # Check if document exists
        cursor.execute("SELECT filename FROM DOCUMENTS WHERE document_id = :doc_id", {"doc_id": doc_id})
        result = cursor.fetchone()
        
        if not result:
            client.close()
            raise HTTPException(status_code=404, detail="Document not found")
        
        filename = result[0]
        
        # Delete chunks first (foreign key constraint)
        cursor.execute("DELETE FROM CHUNKS WHERE document_id = :doc_id", {"doc_id": doc_id})
        chunks_deleted = cursor.rowcount
        
        # Delete document
        cursor.execute("DELETE FROM DOCUMENTS WHERE document_id = :doc_id", {"doc_id": doc_id})
        
        conn.commit()
        client.close()
        
        return {
            "message": f"Document '{filename}' deleted successfully",
            "document_id": doc_id,
            "chunks_deleted": chunks_deleted
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")


@app.post("/api/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    """
    Perform RAG query.
    
    Retrieves relevant document chunks and generates response using LLM.
    """
    try:
        result = ask_query(
            query=request.query,
            document_ids=request.document_ids,
            top_k=request.top_k,
            min_similarity=request.min_similarity,
            config=config,
            stream=False,  # TODO: Implement streaming
            include_embeddings=request.include_embeddings
        )
        
        chunks = [
            ChunkResult(
                chunk_id=chunk['chunk_id'],
                document_id=chunk['document_id'],
                text=chunk['text'],
                similarity_score=chunk['similarity_score'],
                chunk_index=chunk['chunk_index'],
                embedding=chunk.get('embedding') if request.include_embeddings else None
            )
            for chunk in result['results']
        ]
        
        return QueryResponse(
            response=result['response'],
            chunks=chunks,
            query_embedding=result.get('query_embedding'),
            metrics=result['metrics']
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@app.get("/api/models", response_model=ModelsResponse)
async def list_models():
    """List available Ollama models (embedding and chat)."""
    try:
        models = list_available_models(config)
        
        embedding_models = []
        chat_models = []
        
        for model in models.get('models', []):
            model_obj = OllamaModel(
                name=model['name'],
                size=model.get('size', 0),
                modified_at=model.get('modified_at', ''),
                family=model.get('details', {}).get('family'),
                parameter_size=model.get('details', {}).get('parameter_size')
            )
            
            # Categorize models (simple heuristic)
            if 'embed' in model['name'].lower():
                embedding_models.append(model_obj)
            else:
                chat_models.append(model_obj)
        
        return ModelsResponse(
            embedding_models=embedding_models,
            chat_models=chat_models,
            current_embedding_model=config['ollama']['embedding_model'],
            current_chat_model=config['ollama']['chat_model']
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")


@app.get("/api/status", response_model=SystemStatus)
async def get_status():
    """Get system health status."""
    try:
        status = get_overall_status(config)
        
        return SystemStatus(
            healthy=status['healthy'],
            database=ComponentStatus(
                status=status['database']['status'],
                message=status['database']['message']
            ),
            ollama=ComponentStatus(
                status=status['ollama']['status'],
                message=status['ollama']['message']
            ),
            timestamp=datetime.now()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@app.get("/api/stats", response_model=SystemStats)
async def get_stats():
    """Get system statistics."""
    try:
        doc_stats = get_document_stats(config)
        
        # Get vector dimension from config
        dimension = config.get('vector_index', {}).get('dimension', 768)
        index_type = config.get('vector_index', {}).get('index_type', 'HNSW')
        
        return SystemStats(
            total_documents=doc_stats['documents'],
            total_vectors=doc_stats['vectors'],
            total_tokens=doc_stats['total_tokens'],
            embedding_dimension=dimension,
            index_type=index_type
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


def start_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Start the FastAPI server."""
    uvicorn.run(
        "ragcli.api.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


if __name__ == "__main__":
    start_server()

