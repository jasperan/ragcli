"""Main entry point for ragcli CLI."""

import sys
import os
import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
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

# Import commands for direct execution
from .commands.upload import add as upload_cmd
from .commands.query import ask as ask_cmd
from .commands.documents import list_docs, delete as delete_doc
from .commands.visualize import visualize as visualize_cmd
from .commands.db import init as db_init, browse as db_browse, query as db_query, stats as db_stats

app = typer.Typer()
console = Console()

app.add_typer(config_app, name="config")
app.add_typer(documents_app, name="docs")
app.add_typer(visualize_app, name="visualize")
app.add_typer(export_app, name="export")
app.add_typer(db_app, name="db")
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

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    clear_screen()
    config = load_config()
    version = config.get('app', {}).get('version', '1.0.0')
    title = f"""
    ╔════════════════════════════════════════════════════════════════╗
    ║                 RAGCLI INTERFACE                               ║
    ║        Oracle DB 26ai RAG System v{version:<20}         ║
    ╚════════════════════════════════════════════════════════════════╝
    """
    console.print(Panel(title, style="bold cyan", border_style="cyan", subtitle="RAG Management Layer"))
    console.print(f"[dim]Working Directory: {os.getcwd()}[/dim]\n")

def menu_documents():
    while True:
        print_header()
        
        choices = [
            questionary.Choice("List all documents", value="1"),
            questionary.Choice("Delete a document", value="2"),
            questionary.Separator(),
            questionary.Choice("Back to Main Menu", value="0")
        ]
        
        choice = questionary.select(
            "Document Management",
            choices=choices,
            use_arrow_keys=True
        ).ask()
        
        if not choice or choice == "0":
            return
        elif choice == "1":
            list_docs(format="table", verbose=False)
            input("\nPress Enter to continue...")
        elif choice == "2":
            doc_id = Prompt.ask("Enter Document ID to delete")
            if Confirm.ask(f"Are you sure you want to delete {doc_id}?", default=False):
                try:
                    delete_doc(doc_id)
                except Exception as e:
                    console.print(f"[red]Error: {e}[/red]")
            input("\nPress Enter to continue...")

def menu_db():
    while True:
        print_header()
        
        choices = [
            questionary.Choice("Initialize Database (Schemas & Indices)", value="1"),
            questionary.Choice("Browse Tables", value="2"),
            questionary.Choice("Execute SQL Query", value="3"),
            questionary.Choice("Show Statistics", value="4"),
            questionary.Separator(),
            questionary.Choice("Back to Main Menu", value="0")
        ]
        
        choice = questionary.select(
            "Database Management",
            choices=choices,
            use_arrow_keys=True
        ).ask()
        
        if not choice or choice == "0":
            return
        elif choice == "1":
            if Confirm.ask("This will create tables and indices. Continue?", default=True):
                try:
                    db_init()
                except Exception as e:
                    console.print(f"[red]Error: {e}[/red]")
            input("\nPress Enter to continue...")
        elif choice == "2":
            table = questionary.select(
                "Select table",
                choices=["DOCUMENTS", "CHUNKS", "QUERIES"],
                default="DOCUMENTS"
            ).ask()
            limit = IntPrompt.ask("Limit rows", default=20)
            try:
                db_browse(table=table, limit=limit, offset=0)
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
            input("\nPress Enter to continue...")
        elif choice == "3":
            sql = Prompt.ask("Enter SQL SELECT query")
            try:
                db_query(sql=sql, format="table")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
            input("\nPress Enter to continue...")
        elif choice == "4":
            try:
                db_stats()
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
            input("\nPress Enter to continue...")

def menu_visualize():
    print_header()
    console.print("[bold yellow]Visualization[/bold yellow]")
    query = Prompt.ask("Enter query to visualize chain")
    try:
        visualize_cmd(query=query, type="chain")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
    input("\nPress Enter to continue...")


def run_repl():
    """Run the interactive mode with enhanced UI."""
    while True:
        print_header()
        
        choices = [
            questionary.Choice("Upload Document", value="1"),
            questionary.Choice("Ask Question", value="2"),
            questionary.Choice("Manage Documents", value="3"),
            questionary.Choice("Visualize Chain", value="4"),
            questionary.Choice("Database Management", value="5"),
            questionary.Choice("System Status", value="6"),
            questionary.Separator(),
            questionary.Choice("Exit", value="0")
        ]
        
        choice = questionary.select(
            "Select a Task:",
            choices=choices,
            use_arrow_keys=True
        ).ask()
        
        try:
            if not choice or choice == "0":
                console.print("[bold]Goodbye![/bold]")
                break
            elif choice == "1":
                # Interactive upload
                upload_cmd(file_path=None, recursive=False, verbose=True)
                input("\nPress Enter to continue...")
            elif choice == "2":
                # Interactive query
                ask_cmd(query=None, docs=None, top_k=None, threshold=None, show_chain=False, verbose=False)
                input("\nPress Enter to continue...")
            elif choice == "3":
                menu_documents()
            elif choice == "4":
                menu_visualize()
            elif choice == "5":
                menu_db()
            elif choice == "6":
                status_cmd()
                input("\nPress Enter to continue...")
        except Exception as e:
            console.print(f"[bold red]An error occurred:[/bold red] {e}")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    if len(sys.argv) == 1:
        # No args, run REPL
        try:
            run_repl()
        except KeyboardInterrupt:
            sys.exit(0)
    else:
        # Functional mode
        app()

# For entry point compatibility
main = app
