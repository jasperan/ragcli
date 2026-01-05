# ragcli

RAG CLI and REST API for Oracle Database 26ai - Upload documents, query with RAG, and integrate with AnythingLLM for a modern web interface.

ragcli provides a professional terminal interface (Rich-based) and a FastAPI backend for managing RAG workflows. Supports TXT, MD, PDF (with OCR via DeepSeek-OCR), all Ollama models with auto-detection, and Oracle 26ai for vector storage/search.

## Features
- **Enhanced CLI**: REPL mode with rich progress bars, detailed status, database browser, and model management
- **Premium Web Interface**: Clean, "Google-style" React frontend with modern aesthetics and fluid animations
- **FastAPI Backend**: RESTful API for document upload, RAG queries, model listing, and system status
- **AnythingLLM Integration**: Connect with AnythingLLM for an alternative web UI experience
- **Ollama Auto-Detection**: Automatically detect and validate all available Ollama models
- **Core**: Chunking (1000 tokens, 10% overlap), auto vector indexing (HNSW/IVF), metadata tracking, logging/metrics
- **Visualizations**: CLI-based visualizations and Plotly charts for retrieval analysis
- **Deployment**: PyPI, Docker Compose, standalone binary

## Prerequisites
Before running ragcli:
1. **Oracle Database 26ai**: Set up with vector capabilities. Provide username, password, DSN in config.yaml.
2. **Ollama**: Install and run `ollama serve`. Pull models: `ollama pull nomic-embed-text` (embeddings), `ollama pull llama2` (chat).
3. **vLLM for OCR**: Install vLLM, run `python -m vllm.entrypoints.openai.api_server --model deepseek-ai/DeepSeek-OCR --port 8000`.
4. **Python 3.9+**: With pip.

See [Annex A: Detailed Prerequisites](#annex-a-detailed-prerequisites) for setup links.

## Installation

### From Source (Recommended for Development)
```bash
git clone https://github.com/jasperan/ragcli.git
cd ragcli
pip install -r requirements.txt
# Or editable: pip install -e .
```

### PyPI Package (Upcoming)
```bash
pip install ragcli
ragcli config init  # Creates config.yaml from example
```

### Docker Compose (Recommended)
Full stack with ragcli API, AnythingLLM, and Ollama:
```bash
# Create .env file
echo "ORACLE_PASSWORD=your_password" > .env

# Update config.yaml with your Oracle DSN

# Start all services
DOCKER_API_VERSION=1.44 docker-compose up -d

# Pull Ollama models
docker exec ollama ollama pull nomic-embed-text
docker exec ollama ollama pull deepseek-r1

# Access services
# - AnythingLLM UI: http://localhost:3001
# - ragcli API: http://localhost:8000/docs
# - Ollama: http://localhost:11434
```

### Docker (ragcli API only)
```bash
docker build -t ragcli .
docker run -d -p 8000:8000 -v $(pwd)/config.yaml:/app/config.yaml ragcli
```

### Standalone Binary (via PyInstaller)
```bash
pip install pyinstaller
pyinstaller --onefile ragcli/cli/main.py --name ragcli
./ragcli --help
```

## Quick Start
1. **Configure**:
   ```bash
   cp config.yaml.example config.yaml
   # Edit config.yaml: Set oracle DSN/username/password (use ${ENV_VAR} for secrets), ollama endpoint, vllm endpoint.
   # Export env vars if using: export ORACLE_PASSWORD=yourpass
   ```

2. **Initialize Database** (run once):
   ```bash
   ragcli init-db  # Creates tables and indexes in Oracle if they don't exist
   ```

3. **Launch CLI (REPL)**:
   ```bash
   ragcli
   ```
   - Type `help` for commands.
   - Example: `upload document.txt`, `ask "What is RAG?"`, `models list`, `db browse`.

4. **Launch API Server**:
   ```bash
   ragcli api --port 8000
   ```
   - API docs: http://localhost:8000/docs
   - Connect with AnythingLLM or use API directly

5. **Launch Premium Frontend (Optional but Recommended)**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   - Access at: http://localhost:5173
   - Featuring: Google-style search bar, drag-and-drop upload, and animated results.

6. **Functional CLI Example**:
   ```bash
   ragcli upload path/to/doc.pdf
   ragcli ask ask "Summarize the document" --show-chain
   ```

## CLI Usage
- **REPL Mode**: `ragcli` → Interactive shell with tab completion, history.
  - Commands: `upload <path>`, `ask <query>`, `models list`, `db browse`, `status --verbose`, `api`, `exit`.
- **Functional Mode**: `ragcli <command> [options]`.
  - `ragcli upload --recursive folder/` - Upload with progress bars
  - `ragcli ask "query" --docs doc1,doc2 --top-k 3`
  - `ragcli models list` - Show all available Ollama models
  - `ragcli status --verbose` - Detailed vector statistics
  - `ragcli db browse --table DOCUMENTS` - Browse database tables
  - `ragcli db query "SELECT * FROM DOCUMENTS"` - Custom SQL queries
  - See `ragcli --help` for full options.

## Premium Web Interface
The project includes a stunning, minimalist frontend inspired by Google AI Studio.

### Features:
- **Google-Style Search**: A clean, elevated search bar with real-time feedback.
- **Fluid Animations**: Powered by `framer-motion` for a premium feel.
- **Drag-and-Drop**: Easy document ingestion with visual previews.
- **Material 3 Design**: Rounded corners, generous whitespace, and Google Sans typography.

### Usage:
1. Ensure the backend is running: `ragcli api`
2. Start the frontend: `cd frontend && npm run dev`
3. Navigate to `http://localhost:5173`

## API & AnythingLLM Integration
- **FastAPI Backend**: RESTful API with Swagger documentation at `/docs`
- **AnythingLLM**: Modern web UI for document management and chat
- **Docker Compose**: One-command deployment with `docker-compose up -d`
- **API Endpoints**:
  - `POST /api/documents/upload` - Upload documents
  - `GET /api/documents` - List documents
  - `POST /api/query` - RAG query with streaming
  - `GET /api/models` - List Ollama models
  - `GET /api/status` - System health
  - `GET /api/stats` - Database statistics

See [docs/ANYTHINGLLM_INTEGRATION.md](docs/ANYTHINGLLM_INTEGRATION.md) for detailed setup.

## Configuration
Edit `config.yaml`:
- **oracle**: DSN, credentials, TLS (default true).
- **ollama**: Endpoint, auto-detection, models (nomic-embed-text, deepseek-r1), fallback options.
- **api**: Host, port (8000), CORS origins, Swagger docs.
- **ocr**: vLLM endpoint, enabled for PDFs.
- **documents**: Chunk size (1000), overlap (10%), max size (100MB).
- **rag**: Top-k (5), min similarity (0.5).
- **logging**: Level (INFO), file rotation, detailed metrics.

Safe loading handles env vars (e.g., `${ORACLE_PASSWORD}`) and validation.

## New CLI Features

### Enhanced Progress Tracking
Upload documents with real-time progress bars showing:
- File processing status
- Chunking progress
- Embedding generation with ETA
- Database insertion progress

```bash
ragcli upload large_document.pdf
# ... progress bar animation ...
# Then displays summary:
# ╭───────────────────────────────────────────────────── Upload Summary ─────────────────────────────────────────────────────╮
# │ Document ID: 68b152f0-5c22-4952-a552-8bc47de29427                                                                        │
# │ Filename: test_document.txt                                                                                              │
# │ Format: TXT                                                                                                              │
# │ Size: 0.11 KB                                                                                                            │
# │ Chunks: 1                                                                                                                │
# │ Total Tokens: 22                                                                                                         │
# │ Upload Time: 826 ms                                                                                                      │
# ╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

### Detailed Status & Monitoring
```bash
ragcli status --verbose
# ragcli Status                                                        
# ┏━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
# ┃ Component  ┃ Status       ┃ Details                                                                                      ┃
# ┡━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
# │ Database   │ connected    │ Oracle DB connected successfully                                                             │
# │ Documents  │ ok           │ 5 docs, 3 vectors                                                                            │
# │ Ollama     │ connected    │ Ollama connected (24 models)                                                                 │
# │ Overall    │ issues       │ Some issues detected                                                                         │
# └────────────┴──────────────┴──────────────────────────────────────────────────────────────────────────────────────────────┘
#
# ═══ Vector Statistics ═══
# ... (tables for Vector Config, Storage, Performance)

### Interactive Database Browser
```bash
ragcli db browse --table DOCUMENTS --limit 20
# DOCUMENTS (Rows 1-5 of 6)                                                  
# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
# ┃ ID                               ┃ Filename          ┃ Format ┃ Size (KB) ┃ Chunks ┃ Tokens ┃ Uploaded                   ┃
# ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
# │ 68b152f0-5c22...    │ test_document.txt │ TXT    │ 0.11      │ 1      │ 22     │ 2026-01-05 16:34:47.038679 │
# └──────────────────────────────────┴───────────────────┴────────┴───────────┴────────┴────────┴────────────────────────────┘

ragcli db query "SELECT * FROM DOCUMENTS WHERE file_format='PDF'"
ragcli db stats
```
Browse tables with pagination, execute custom SQL queries, view database statistics.

### Model Management
```bash
ragcli models list
# ┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
# ┃ Model Name              ┃ Type      ┃ Size     ┃ Modified            ┃
# ┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
# │ gemma3:270m             │ Chat/LLM  │ 0.27 GB  │ 2026-01-05T15:00:52 │
# │ deepseek-r1:latest      │ Chat/LLM  │ 4.36 GB  │ 2025-04-11T18:39:00 │
# │ nomic-embed-text:latest │ Embedding │ 0.26 GB  │ 2025-11-14T21:38:46 │
# └─────────────────────────┴───────────┴──────────┴─────────────────────┘

ragcli models validate                # Validate configured models
ragcli models check llama3            # Check if specific model exists
```

## Troubleshooting
- **Ollama unreachable**: Run `ollama serve` and check endpoint. Use `ragcli models list` to verify.
- **Oracle DPY-1005 (Busy Connection)**: Fixed! Ensure you are using the latest version which properly handles connection pooling and closure.
- **Oracle ORA-01745/01484 (Vector Ingestion)**: Fixed! Vector ingestion now uses robust `TO_VECTOR` with JSON-serialized input for maximum compatibility.
- **Looping/Stuck Upload**: Fixed! Corrected infinite loop in `chunk_text` for small documents (<100 tokens).
- **OCR errors**: Ensure vLLM is running with DeepSeek-OCR model. Verify `config.yaml` points to the correct port (default 8001 to avoid API conflict).
- **Model not found**: Run `ragcli models validate` for suggestions. Pull with `ollama pull <model>`.
- **API connection**: Check `ragcli api` is running. Test with `curl http://localhost:8000/api/status`.
- **Logs**: Check `./logs/ragcli.log` for details (DEBUG mode for verbose).

For issues, run with `--debug` or set `app.debug: true`.

## Annex A: Detailed Prerequisites
- **Ollama**: https://ollama.com/ - `curl -fsSL https://ollama.com/install.sh | sh`
- **vLLM**: `pip install vllm` - See https://docs.vllm.ai/en/latest/
- **Oracle 26ai**: Enable vector search; connect via oracledb (no wallet needed for TLS).
- **Models**: Ensure pulled in Ollama; DeepSeek-OCR in vLLM (HuggingFace).

## Annex B: Full Specification
See `.clinerules/ragcli-formal.md` for architecture, schemas, workflows.

## Contributing
See docs/CONTRIBUTING.md (to be added).

## License
MIT
