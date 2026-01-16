"""Query commands for ragcli CLI."""

import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint
from rich.prompt import Prompt
from ragcli.core.rag_engine import ask_query
from ragcli.config.config_manager import load_config
from typing import List, Optional

app = typer.Typer()
console = Console()

@app.command()
def ask(
    query: Optional[str] = typer.Argument(None, help="Question to ask"),
    docs: Optional[List[str]] = typer.Option(None, "--docs", help="Comma-separated document IDs"),
    top_k: Optional[int] = typer.Option(None, "--top-k", help="Number of top results"),
    threshold: Optional[float] = typer.Option(None, "--threshold", "-t", help="Min similarity score"),
    show_chain: bool = typer.Option(False, "--show-chain", "-c", help="Show retrieval chain"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose metrics")
):
    """Ask a question against the documents."""
    config = load_config()
    
    if query is None:
        query = Prompt.ask("Enter your question")

    document_ids = docs.split(',') if docs else None
    
    try:
        result = ask_query(query, document_ids, top_k, threshold, config)
        
        # Response
        rprint(typer.style("Answer:", bold=True))
        rprint(result['response'])
        
        # Results
        if show_chain or verbose:
            table = Table(title="Retrieval Results")
            table.add_column("Document ID", style="cyan")
            table.add_column("Chunk", justify="right")
            table.add_column("Similarity", justify="right")
            table.add_column("Excerpt")
            
            for r in result['results']:
                table.add_row(
                    r['document_id'],
                    str(r['chunk_number']),
                    f"{r['similarity_score']:.3f}",
                    r['text']
                )
            console.print(table)
        
        # Metrics
        if verbose:
            rprint(typer.style("Metrics:", bold=True))
            for k, v in result['metrics'].items():
                rprint(f"{k}: {v}")
                
    except Exception as e:
        rprint(typer.style(f"Query failed: {e}", fg=typer.colors.RED))
        raise typer.Exit(1)

if __name__ == "__main__":
    app()
