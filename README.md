# ragcli

RAG CLI and Web UI for Oracle Database 26ai - Upload documents, query with RAG, visualize retrieval chains and embeddings in real-time.

ragcli provides a professional terminal interface (Rich-based) and a beautiful web UI (Gradio-like, dark mode) for managing RAG workflows. Supports TXT, MD, PDF (with OCR via DeepSeek-OCR), Ollama for embeddings/LLM, and Oracle 26ai for vector storage/search.

## Features
- **CLI**: REPL mode with commands (upload, ask, list-docs, visualize, etc.) + functional mode.
- **Web UI**: Tabs for Dashboard, Upload, Ask (real-time query), Documents, Visualize (3D embeddings, heatmaps), Settings.
- **Core**: Chunking (1000 tokens, 10% overlap), auto vector indexing (HNSW/IVF), metadata tracking, logging/metrics.
- **Visualizations**: Retrieval chain flow, embedding space (UMAP 2D/3D), similarity heatmaps, live search updates.
- **Deployment**: PyPI, Docker, standalone binary.

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
git clone https://github.com/user/ragcli.git
cd ragcli
pip install -r requirements.txt
# Or editable: pip install -e .
```

### PyPI Package (Upcoming)
```bash
pip install ragcli
ragcli config init  # Creates config.yaml from example
```

### Docker
```bash
docker build -t ragcli .
docker run -it -p 7860:7860 -v $(pwd)/config.yaml:/app/config.yaml ragcli  # Mount config
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
   - Example: `upload document.txt`, `ask "What is RAG?"`, `list-docs`.

4. **Launch Web UI**:
   ```bash
   ragcli web
   ```
   - Open http://localhost:7860.
   - Upload files in Upload tab, query in Ask tab, visualize in Visualize tab.

5. **Functional CLI Example**:
   ```bash
   ragcli upload path/to/doc.pdf
   ragcli ask "Summarize the document" --show-chain
   ```

## CLI Usage
- **REPL Mode**: `ragcli` → Interactive shell with tab completion, history.
  - Commands: `upload <path>`, `ask <query>`, `list-docs`, `visualize <query_id>`, `web`, `exit`.
- **Functional Mode**: `ragcli <command> [options]`.
  - `ragcli upload --recursive folder/`
  - `ragcli ask "query" --docs doc1,doc2 --top-k 3`
  - See `ragcli --help` for full options.

## Web UI
- **Dark Theme**: Professional Gradio interface with cyan accents.
- **Real-time**: Type query for live similarity previews.
- **Tabs**: Dashboard (stats), Upload (drag-drop), Ask (stream response), Documents (table/actions), Visualize (Plotly plots), Settings (edit config).

## Configuration
Edit `config.yaml`:
- **oracle**: DSN, credentials, TLS (default true).
- **ollama**: Endpoint, models (nomic-embed-text, llama2).
- **ocr**: vLLM endpoint, enabled for PDFs.
- **documents**: Chunk size (1000), overlap (10%), max size (100MB).
- **rag**: Top-k (5), min similarity (0.5).
- **logging**: Level (INFO), file rotation.
- **ui**: Port (7860), theme (dark).

Safe loading handles env vars (e.g., `${ORACLE_PASSWORD}`) and validation.

## Troubleshooting
- **Ollama unreachable**: Run `ollama serve` and check endpoint.
- **Oracle connection failed**: Verify DSN/credentials, TLS settings.
- **OCR errors**: Ensure vLLM running with DeepSeek-OCR model.
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
