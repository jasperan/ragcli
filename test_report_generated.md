# ragcli End-to-End Test Report

### Help Command
```bash
$ ragcli --help
Usage: ragcli [OPTIONS] COMMAND [ARGS]...                                                                                  
                                                                                                                            
╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion          Install completion for the current shell.                                                  │
│ --show-completion             Show completion for the current shell, to copy it or customize the installation.           │
│ --help                        Show this message and exit.                                                                │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ upload      Upload document(s) to the vector store.                                                                      │
│ ask         Ask a question against the documents.                                                                        │
│ status      Check system status: DB, APIs, documents, vectors.                                                           │
│ api         Launch the FastAPI server for AnythingLLM integration.                                                       │
│ init-db     Alias for db init.                                                                                           │
│ config                                                                                                                   │
│ docs                                                                                                                     │
│ visualize                                                                                                                │
│ export                                                                                                                   │
│ db                                                                                                                       │
│ models                                                                                                                   │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

### List Models
```bash
$ ragcli models list
Available Ollama Models                         
┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
┃ Model Name              ┃ Type      ┃ Size     ┃ Modified            ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
│ gemma3:270m             │ Chat/LLM  │ 0.27 GB  │ 2026-01-05T15:00:52 │
│ gemma3:1b-it-qat        │ Chat/LLM  │ 0.93 GB  │ 2026-01-04T20:21:50 │
│ gemma3:4b-it-qat        │ Chat/LLM  │ 3.73 GB  │ 2026-01-04T18:13:09 │
│ mistral:latest          │ Chat/LLM  │ 4.07 GB  │ 2025-12-15T05:02:50 │
│ smollm2:135m            │ Chat/LLM  │ 0.25 GB  │ 2025-12-10T17:18:01 │
│ qwen3:0.6b              │ Chat/LLM  │ 0.49 GB  │ 2025-11-17T12:02:07 │
│ deepseek-r1:1.5b        │ Chat/LLM  │ 1.04 GB  │ 2025-11-17T12:02:00 │
│ qwen2.5:7b              │ Chat/LLM  │ 4.36 GB  │ 2025-11-17T10:43:24 │
│ mistral:7b              │ Chat/LLM  │ 4.07 GB  │ 2025-11-17T09:29:44 │
│ llama3.2:3b             │ Chat/LLM  │ 1.88 GB  │ 2025-11-17T09:29:44 │
│ phi3:3.8b               │ Chat/LLM  │ 2.03 GB  │ 2025-11-17T09:29:43 │
│ nomic-embed-text:latest │ Embedding │ 0.26 GB  │ 2025-11-14T21:38:46 │
│ phi3:latest             │ Chat/LLM  │ 2.03 GB  │ 2025-07-08T10:49:25 │
│ mattw/pygmalion:latest  │ Chat/LLM  │ 3.56 GB  │ 2025-06-30T01:46:29 │
│ mario:latest            │ Chat/LLM  │ 1.88 GB  │ 2025-06-30T01:46:29 │
│ llama3-backup:latest    │ Chat/LLM  │ 1.88 GB  │ 2025-06-30T01:46:29 │
│ llama3.2:latest         │ Chat/LLM  │ 1.88 GB  │ 2025-06-28T03:16:35 │
│ qwq:latest              │ Chat/LLM  │ 18.49 GB │ 2025-05-05T22:01:26 │
│ phi4:latest             │ Chat/LLM  │ 8.43 GB  │ 2025-04-12T00:02:39 │
│ llama2:latest           │ Chat/LLM  │ 3.56 GB  │ 2025-04-11T23:23:22 │
│ llama2:7b               │ Chat/LLM  │ 3.56 GB  │ 2025-04-11T23:23:06 │
│ qwen2:latest            │ Chat/LLM  │ 4.13 GB  │ 2025-04-11T22:41:30 │
│ deepseek-r1:latest      │ Chat/LLM  │ 4.36 GB  │ 2025-04-11T18:39:00 │
│ llama3:latest           │ Chat/LLM  │ 4.34 GB  │ 2025-03-25T12:20:34 │
└─────────────────────────┴───────────┴──────────┴─────────────────────┘

Current Configuration:
  Embedding Model: nomic-embed-text
  Chat Model: deepseek-r1:latest
```

### Initialize Database
```bash
$ ragcli init-db
WARNING: Skipping vector index creation due to unsupported syntax in current Oracle Database version.
Vector search will work but may be slower without an index. Please ensure Oracle Database 23ai or later is used.
Database already initialized.
✓ Database initialized successfully!
```

### System Status
```bash
$ ragcli status --verbose
ragcli Status                                                        
┏━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Component  ┃ Status       ┃ Details                                                                                      ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Database   │ connected    │ Oracle DB connected successfully                                                             │
│ Documents  │ ok           │ 5 docs, 3 vectors                                                                            │
│ Ollama     │ connected    │ Ollama connected (24 models)                                                                 │
│ vLLM (OCR) │ disconnected │ vLLM unreachable: HTTPConnectionPool(host='localhost', port=8001): Max retries exceeded with │
│            │              │ url: /health (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at     │
│            │              │ 0x7ad1119bc920>: Failed to establish a new connection: [Errno 111] Connection refused'))     │
│ Overall    │ issues       │ Some issues detected                                                                         │
└────────────┴──────────────┴──────────────────────────────────────────────────────────────────────────────────────────────┘

═══ Vector Statistics ═══

           Vector Configuration            
┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ Parameter            ┃ Value            ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ Embedding Dimension  │ 768              │
│ Index Type           │ HNSW             │
│ Embedding Model      │ nomic-embed-text │
│ HNSW M Parameter     │ 16               │
│ HNSW EF Construction │ 200              │
└──────────────────────┴──────────────────┘

        Storage Statistics         
┏━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Metric                ┃ Value   ┃
┡━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩
│ Total Vectors         │ 3       │
│ Estimated Vector Size │ 0.01 MB │
│ Total Documents       │ 5       │
│ Total Tokens          │ 270     │
│ Avg Chunks per Doc    │ 0.6     │
└───────────────────────┴─────────┘

      Performance Metrics       
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Metric             ┃ Value   ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩
│ Avg Search Latency │ 0.00 ms │
│ Cache Hit Rate     │ 0.0%    │
└────────────────────┴─────────┘
```

### Upload Document
```bash
$ ragcli upload test_document.txt
✓ Upload successful!
╭───────────────────────────────────────────────────── Upload Summary ─────────────────────────────────────────────────────╮
│ Document ID: 68b152f0-5c22-4952-a552-8bc47de29427                                                                        │
│ Filename: test_document.txt                                                                                              │
│ Format: TXT                                                                                                              │
│ Size: 0.11 KB                                                                                                            │
│ Chunks: 1                                                                                                                │
│ Total Tokens: 22                                                                                                         │
│ Upload Time: 826 ms                                                                                                      │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

### Ask Question
```bash
$ ragcli ask "What is in the test document?"
[1mAnswer:[0m
<think>
Okay, so I need to figure out what's in the test documents provided. Let me start by looking at each context line.

First two lines mention "test document for ragcli" and talk about verifying upload and retrieval processes. So they probably
have sample text there.

Next two lines are similar but specify it's a small test document for RAG, focusing on chunking verification. They also list
RAG as Retrieval-Augmented Generation, Google Style for the frontend, Oracle 26ai as the database, and Ollama as the LLM 
provider.

So putting it together, each test document has sample text for upload and retrieval (and chunking in the small ones). It 
includes info about RAG components: its purpose, database, and LLM. The user is asking what's inside these tests, so I 
should list both types of documents with their contents.
</think>

The test documents contain sample text to verify the upload and retrieval processes. There are two main types:

1. **Large Test Document**: Includes sample text for both upload and chunking verification, as well as details about RAG 
(Retrieval-Augmented Generation), Google Style formatting, Oracle 26ai database usage, and Ollama as the LLM provider.

2. **Small Test Document**: Focuses on verifying the upload and chunking processes with sample text, while also providing 
information about RAG, Google Style, Oracle 26ai, and Ollama.

Both documents are designed to ensure proper functionality of the RAG system components.
```

### Database Stats
```bash
$ ragcli db stats
Database Statistics             
┏━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
┃ Table     ┃ Row Count ┃ Size Info         ┃
┡━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
│ DOCUMENTS │ 6         │ Total: 0.00 MB    │
│ CHUNKS    │ 4         │ Total tokens: 168 │
│ QUERIES   │ 3         │ -                 │
└───────────┴───────────┴───────────────────┘
```

### Browse Documents Table
```bash
$ ragcli db browse --table DOCUMENTS --limit 5
DOCUMENTS (Rows 1-5 of 6)                                                  
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ID                               ┃ Filename          ┃ Format ┃ Size (KB) ┃ Chunks ┃ Tokens ┃ Uploaded                   ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 68b152f0-5c22-4952-a552-8bc47de… │ test_document.txt │ TXT    │ 0.11      │ 1      │ 22     │ 2026-01-05 16:34:47.038679 │
│ 2be09ba2-7d35-4126-90b5-b3ee16e… │ test_document.txt │ TXT    │ 0.11      │ 1      │ 22     │ 2026-01-05 16:33:20.628989 │
│ dd3f774f-c220-4af9-8de9-eae3156… │ test_small.txt    │ TXT    │ 0.26      │ 1      │ 62     │ 2026-01-04 15:04:18.109161 │
│ 7cb7ad80-7bae-41fd-a9c0-6f223c1… │ test_small.txt    │ TXT    │ 0.26      │ 1      │ 62     │ 2026-01-04 15:04:04.681687 │
│ ac4f9265-cde9-4782-b00b-2774aae… │ test_small.txt    │ TXT    │ 0.26      │ 1      │ 62     │ 2026-01-04 15:03:25.368468 │
└──────────────────────────────────┴───────────────────┴────────┴───────────┴────────┴────────┴────────────────────────────┘

Next: --offset 5
```

