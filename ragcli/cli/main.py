"""Main entry point for ragcli CLI."""

import sys
import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich import print as rprint
from .commands.config import config_app
from .commands.upload import app as upload_app
from .commands.query import app as query_app
from .commands.documents import app as documents_app
from .commands.visualize import app as visualize_app
from .commands.export import app as export_app
from .commands.db import app as db_app
from .commands.status import app as status_app
from .commands.models import app as models_app
from ..config.config_manager import load_config

app = typer.Typer()
console = Console()

app.add_typer(config_app, name="config")
# app.add_typer(upload_app, name="upload") # Deprecated: exposed as single command
# app.add_typer(query_app, name="ask")     # Deprecated: exposed as single command
app.add_typer(documents_app, name="docs")
app.add_typer(visualize_app, name="visualize")
app.add_typer(export_app, name="export")
app.add_typer(db_app, name="db")
# app.add_typer(status_app, name="status") # Deprecated: exposed as single command
app.add_typer(models_app, name="models")

# Expose commands directly
from .commands.upload import add as upload_cmd
from .commands.query import ask as ask_cmd
from .commands.status import status as status_cmd

app.command(name="upload")(upload_cmd)
app.command(name="ask")(ask_cmd)
app.command(name="status")(status_cmd)

@app.command()
def api(
    host: str = typer.Option("0.0.0.0", "--host", "-h"),
    port: int = typer.Option(8000, "--port", "-p"),
    reload: bool = typer.Option(False, "--reload")
):
    """Launch the FastAPI server for AnythingLLM integration."""
    from ragcli.api.server import start_server
    console.print(f"[cyan]Starting ragcli API server on {host}:{port}[/cyan]")
    console.print(f"[cyan]API docs available at: http://{host}:{port}/docs[/cyan]")
    start_server(host=host, port=port, reload=reload)

@app.command()
def init_db():
    """Alias for db init."""
    from .commands.db import init
    init()

def show_help():
    """Show available commands."""
    help_text = """
Commands:
  📤 upload <file_path>           Upload document(s)
  ❓ ask <query>                  Ask question (select docs optionally)
  📋 docs list                    List all documents
  🗑️ docs delete <doc_id>         Delete document
  📊 visualize <query>            Visualize retrieval chain
  💾 export --logs                Export session logs
  ⚙️ config show                  Show current configuration
  🔍 status                       Check system status
  🤖 models list                  List available Ollama models
  🌐 api                          Launch FastAPI server (AnythingLLM)
  🔧 db init                      Initialize database
  🔍 db browse                    Browse database tables
  ❓ help                         Show help
  🚪 exit                         Exit application
    """
    console.print(Panel(help_text, title="ragcli Commands", border_style="blue"))

def parse_and_run(command: str) -> bool:
    """Parse command and run if valid."""
    parts = command.strip().split()
    if not parts:
        return True
    
    cmd = parts[0]
    args = parts[1:]
    
    command_map = {
        'upload': lambda: typer.run(upload_app, [cmd] + args),
        'ask': lambda: typer.run(query_app, [cmd] + args),
        'docs': lambda: typer.run(documents_app, [cmd] + args),
        'visualize': lambda: typer.run(visualize_app, [cmd] + args),
        'export': lambda: typer.run(export_app, [cmd] + args),
        'config': lambda: typer.run(config_app, [cmd] + args),
        'db': lambda: typer.run(db_app, [cmd] + args),
        'status': lambda: typer.run(status_app, [cmd] + args),
        'models': lambda: typer.run(models_app, [cmd] + args),
        'api': lambda: api(),
        'help': lambda: show_help(),
        'exit': lambda: False,
        'quit': lambda: False,
    }
    
    if cmd in command_map:
        try:
            return command_map[cmd]()
        except Exception as e:
            rprint(typer.style(f"Error in {cmd}: {e}", fg=typer.colors.RED))
            return True
    else:
        rprint(typer.style(f"Unknown command: {cmd}. Type 'help' for list.", fg=typer.colors.YELLOW))
        return True

def run_repl():
    """Run the REPL mode."""
    config = load_config()
    rprint(Panel(f"Welcome to {config['app']['app_name']} v{config['app']['version']} - Oracle DB 26ai RAG Interface", title="ragcli", border_style="cyan"))
    rprint("Type 'help' for available commands")
    
    while True:
        try:
            command = Prompt.ask("ragcli")
            if not parse_and_run(command):
                break
        except KeyboardInterrupt:
            rprint("\nExiting...")
            break
        except Exception as e:
            rprint(typer.style(f"Unexpected error: {e}", fg=typer.colors.RED))

if __name__ == "__main__":
    if len(sys.argv) == 1:
        # No args, run REPL
        run_repl()
    else:
        # Functional mode
        app()

# For entry point compatibility
main = app
