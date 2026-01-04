# AnythingLLM Integration Guide

This guide explains how to integrate ragcli with AnythingLLM for a modern, feature-rich web interface powered by your Oracle 26ai vector database.

## Overview

ragcli now provides a FastAPI backend that can be used with AnythingLLM's frontend. This architecture gives you:

- **Modern UI**: AnythingLLM's polished interface for document management and chat
- **Oracle 26ai Backend**: Your existing vector database and RAG pipeline
- **Ollama Support**: All Ollama models automatically detected and available
- **RESTful API**: Clean API for custom integrations

## Architecture

```
┌─────────────────┐         ┌──────────────┐         ┌──────────────────┐
│  AnythingLLM    │   HTTP  │   ragcli     │  SQL    │  Oracle DB 26ai  │
│   Frontend      │────────>│   FastAPI    │────────>│  (Vectors)       │
└─────────────────┘         │   Backend    │         └──────────────────┘
                            └──────────────┘
                                    │
                                    │ HTTP
                                    v
                            ┌──────────────┐
                            │   Ollama     │
                            │   (LLMs)     │
                            └──────────────┘
```

## Quick Start with Docker Compose

The easiest way to get started is with Docker Compose:

### 1. Configure Environment

Edit `config.yaml` with your Oracle database credentials and Ollama endpoint.

### 2. Launch Services

```bash
docker-compose up -d
```

This starts:
- **ragcli-api**: FastAPI server on port 8000
- **anythingllm**: Web UI on port 3001
- **ollama**: LLM server on port 11434

### 3. Access AnythingLLM

Open http://localhost:3001 in your browser and configure:

1. **LLM Provider**: Select "Custom OpenAI" or "Ollama"
   - Endpoint: `http://ollama:11434`
   - Model: Any model from `ragcli models list`

2. **Vector Database**: Use ragcli API endpoints
   - Upload endpoint: `http://ragcli-api:8000/api/documents/upload`
   - Query endpoint: `http://ragcli-api:8000/api/query`

## Manual Installation

### Option 1: Desktop AnythingLLM + Local ragcli

1. **Install AnythingLLM Desktop**
   - Download from: https://anythingllm.com/
   - Install for your platform (Mac/Windows/Linux)

2. **Start ragcli API server**
   ```bash
   cd ragcli
   ragcli api --port 8000
   ```

3. **Configure AnythingLLM**
   - Open AnythingLLM Desktop
   - Settings → LLM Provider → "Ollama" or "Custom"
   - Endpoint: `http://localhost:11434` (Ollama)
   - API Endpoint: `http://localhost:8000` (ragcli)

### Option 2: Docker AnythingLLM + Local ragcli

1. **Start Ollama**
   ```bash
   ollama serve
   ```

2. **Start ragcli API**
   ```bash
   ragcli api --host 0.0.0.0 --port 8000
   ```

3. **Run AnythingLLM in Docker**
   ```bash
   docker run -d -p 3001:3001 \
     -v anythingllm-storage:/app/server/storage \
     --name anythingllm \
     mintplexlabs/anythingllm:latest
   ```

4. **Access UI**: http://localhost:3001

## API Endpoints

ragcli provides these endpoints for AnythingLLM integration:

### Documents

- `POST /api/documents/upload` - Upload document
- `GET /api/documents` - List all documents
- `DELETE /api/documents/{doc_id}` - Delete document

### Query

- `POST /api/query` - Perform RAG query
  ```json
  {
    "query": "What is RAG?",
    "top_k": 5,
    "min_similarity": 0.5,
    "document_ids": ["optional-filter"]
  }
  ```

### Models

- `GET /api/models` - List available Ollama models

### Status

- `GET /api/status` - System health check
- `GET /api/stats` - Database statistics

### API Documentation

Visit `http://localhost:8000/docs` for interactive API documentation (Swagger UI).

## Configuration

### ragcli Configuration (config.yaml)

```yaml
api:
  host: "0.0.0.0"
  port: 8000
  cors_origins:
    - "http://localhost:3001"  # AnythingLLM URL
    - "*"                       # Or allow all (dev only)
  enable_swagger: true

ollama:
  endpoint: "http://localhost:11434"
  auto_detect_models: true
  embedding_model: "nomic-embed-text"
  chat_model: "deepseek-r1:latest"
```

### AnythingLLM Configuration

1. **LLM Settings**
   - Provider: Ollama or Custom OpenAI-compatible
   - Endpoint: Your Ollama URL
   - Model: Select from dropdown (auto-populated from Ollama)

2. **Embedding Settings**
   - Provider: Ollama
   - Model: nomic-embed-text (recommended) or other embedding model

3. **Vector Database**
   - Type: Custom (via ragcli API)
   - Configure endpoints to point to ragcli API

## Using Ollama Models

ragcli automatically detects all available Ollama models:

### List Available Models
```bash
ragcli models list
```

### Validate Configuration
```bash
ragcli models validate
```

### Check Specific Model
```bash
ragcli models check llama3
```

### Pull New Models
```bash
ollama pull llama3
ollama pull nomic-embed-text
ragcli models validate  # Verify ragcli can see them
```

## CLI Enhancements

New CLI commands with enhanced verbosity:

### Upload with Progress
```bash
ragcli upload document.pdf
# Shows: File processing, chunking, embedding progress with ETA
```

### Detailed Status
```bash
ragcli status --verbose
# Shows: Vector statistics, index metadata, performance metrics
```

### Database Browser
```bash
ragcli db browse --table DOCUMENTS --limit 50
ragcli db query "SELECT * FROM DOCUMENTS WHERE file_format='PDF'"
ragcli db stats
```

## Troubleshooting

### API Connection Issues

**Problem**: AnythingLLM can't reach ragcli API

**Solutions**:
- Check API is running: `curl http://localhost:8000/`
- Verify CORS settings in `config.yaml`
- For Docker: Use container names (e.g., `http://ragcli-api:8000`)

### Model Not Found

**Problem**: Configured model not available

**Solutions**:
```bash
ragcli models list          # Check available models
ollama pull model-name      # Pull missing model
ragcli models validate      # Verify configuration
```

### Database Connection Failed

**Problem**: Oracle connection errors

**Solutions**:
- Verify Oracle credentials in `config.yaml`
- Check network connectivity
- Initialize database: `ragcli db init`
- Check status: `ragcli status`

### Upload Fails

**Problem**: Document upload returns error

**Solutions**:
- Check file format (TXT, MD, PDF supported)
- Verify file size under 100MB (configurable)
- For PDFs: Ensure vLLM OCR service is running
- Check logs: `tail -f logs/ragcli.log`

## Performance Tuning

### Vector Index Optimization

For large datasets (>100k vectors):

```yaml
vector_index:
  index_type: "HYBRID"  # Best for large datasets
  m: 32                 # Increase for better recall
  ef_construction: 400  # Increase for better quality
```

### Chunking Strategy

Adjust based on your documents:

```yaml
documents:
  chunk_size: 1500      # Increase for longer context
  chunk_overlap_percentage: 15  # More overlap = better continuity
```

### RAG Parameters

```yaml
rag:
  top_k: 10             # Retrieve more chunks
  min_similarity_score: 0.6  # Higher = stricter matching
```

## Advanced Usage

### Custom Integration

Use ragcli API in your own applications:

```python
import requests

# Upload document
with open('document.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/documents/upload',
        files={'file': f}
    )
    doc_id = response.json()['document_id']

# Query
query_response = requests.post(
    'http://localhost:8000/api/query',
    json={
        'query': 'What is this document about?',
        'document_ids': [doc_id],
        'top_k': 5
    }
)
answer = query_response.json()['response']
```

### Multiple Ollama Instances

Run different models on different ports:

```bash
# Terminal 1: Embedding model
OLLAMA_HOST=0.0.0.0:11434 ollama serve

# Terminal 2: Chat model
OLLAMA_HOST=0.0.0.0:11435 ollama serve
```

Update config.yaml to use appropriate endpoints.

## Security Considerations

### Production Deployment

1. **CORS**: Restrict origins in production
   ```yaml
   api:
     cors_origins:
       - "https://your-domain.com"
   ```

2. **Authentication**: Add API key middleware (FastAPI)
3. **HTTPS**: Use reverse proxy (nginx, traefik)
4. **Firewall**: Restrict database access
5. **Secrets**: Use environment variables for credentials

### Docker Security

```yaml
# docker-compose.yml
services:
  ragcli-api:
    environment:
      - ORACLE_PASSWORD=${ORACLE_PASSWORD}  # From .env file
```

Create `.env`:
```
ORACLE_PASSWORD=your_secure_password
```

## Support & Resources

- **ragcli Documentation**: See README.md
- **AnythingLLM Docs**: https://docs.anythingllm.com/
- **Ollama Models**: https://ollama.com/library
- **Oracle 26ai**: https://docs.oracle.com/database/

## Example Workflows

### 1. Knowledge Base Setup

```bash
# Initialize database
ragcli db init

# Validate models
ragcli models validate

# Upload documents
ragcli upload --recursive /path/to/docs/

# Check status
ragcli status --verbose

# Start API
ragcli api
```

### 2. Interactive Usage

Open AnythingLLM → Upload documents via UI → Chat with your documents

### 3. Monitoring

```bash
# Database statistics
ragcli db stats

# Browse documents
ragcli db browse --table DOCUMENTS

# Check vector index
ragcli status --verbose
```

---

**Questions?** Open an issue on GitHub or check the main README.md for more details.

