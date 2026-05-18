# ragcli-tui

Terminal dashboard for ragcli, built in Rust with [ratatui](https://ratatui.rs/).

## Build

```bash
cd tui
cargo build --release
# Binary: tui/target/release/ragcli-tui
```

## Run

```bash
# From the ragcli project root:
./tui/target/release/ragcli-tui

# Custom API port:
RAGCLI_PORT=9000 ./tui/target/release/ragcli-tui

# Custom project root:
RAGCLI_ROOT=/path/to/ragcli ./tui/target/release/ragcli-tui

# Connect to an already-running API instead of spawning one:
RAGCLI_API_URL=http://localhost:8000 ./tui/target/release/ragcli-tui
```

By default the binary starts `ragcli api`, waits for it to be healthy, then renders the dashboard. In a source checkout it uses `python3 ragcli.py api`; from an installed package it falls back to the `ragcli` console command. Set `RAGCLI_API_URL` to connect to an API that is already running.

## Views

| # | Name | What it shows |
|---|------|--------------|
| 1 | Query | Streaming RAG queries with source chunks |
| 2 | Heatmap | Color-coded embedding visualization |
| 3 | Graph | Interactive knowledge graph explorer |
| 4 | Agents | CoT agent pipeline trace |
| 5 | Docs | Document management and chunk preview |
| 6 | System | Service health, latency, and models |

## Keybindings

```
q          Quit
1-6        Switch view
Tab        Next view
/          Command palette
?          Help overlay
r          Refresh data in Docs/System views
d,d        Confirm document deletion in Docs view
```

## Requirements

- Rust 1.70+ and Cargo
- Python 3.9+ with ragcli installed or a source checkout
- Running Ollama instance
- Oracle Database 26ai
