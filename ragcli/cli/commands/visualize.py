"""Visualization commands for ragcli CLI."""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint
from ragcli.config.config_manager import load_config
from ragcli.database.oracle_client import OracleClient
from ragcli.core.oracle_integration import OracleIntegrationManager
from typing import Optional

app = typer.Typer()
console = Console()


@app.command()
def visualize(
    query: Optional[str] = None,
    type: str = typer.Option("chain", "--type", "-t", help="Visualization type (chain, embedding)")
):
    """Visualize text tokenization and embedding using Oracle AI."""
    config = load_config()
    
    if not query:
        rprint("[yellow]Provide text to visualize with --query or enter it below.[/yellow]")
        query = console.input("   Enter text: ")
        if not query:
            rprint("[red]No input provided.[/red]")
            raise typer.Exit(1)

    client = OracleClient(config)
    conn = None
    
    try:
        conn = client.get_connection()
        manager = OracleIntegrationManager(conn)
        
        # Step 1: Chunking with OracleTextSplitter
        console.print("\n[bold cyan]═══ Tokenization (OracleTextSplitter) ═══[/bold cyan]")
        
        # Use sentence-based splitting for visualization
        split_params = {"by": "words", "split": "sentence", "max": 100, "normalize": "all"}
        chunks = manager.split_text(text=query, params=split_params)
        
        if not chunks:
            console.print("[yellow]No chunks generated from input.[/yellow]")
            return
        
        chunk_table = Table(show_header=True, header_style="bold #a855f7", box=None)
        chunk_table.add_column("#", style="dim", width=4)
        chunk_table.add_column("Chunk Content", style="white")
        chunk_table.add_column("Length", style="cyan", justify="right")
        
        for i, chunk in enumerate(chunks, 1):
            preview = chunk[:80] + "..." if len(chunk) > 80 else chunk
            chunk_table.add_row(str(i), preview, f"{len(chunk)} chars")
        
        console.print(chunk_table)
        console.print(f"\n   [dim]Total chunks: {len(chunks)}[/dim]")
        
        # Step 2: Embeddings with OracleEmbeddings
        console.print("\n[bold cyan]═══ Embeddings (OracleEmbeddings) ═══[/bold cyan]")
        
        embed_params = {"provider": "database", "model": "ALL_MINILM_L12_V2"}
        embeddings = manager.generate_embeddings(chunks, params=embed_params)
        
        if embeddings and len(embeddings) > 0:
            dim = len(embeddings[0])
            console.print(f"   [bold]Model:[/bold] ALL_MINILM_L12_V2 | [bold]Dimension:[/bold] {dim}")
            
            embed_table = Table(show_header=True, header_style="bold #a855f7", box=None)
            embed_table.add_column("Chunk", style="dim", width=8)
            embed_table.add_column("Vector Preview (first 5 values)", style="white")
            
            for i, vec in enumerate(embeddings, 1):
                preview_vals = ", ".join([f"{v:.4f}" for v in vec[:5]])
                embed_table.add_row(f"Chunk {i}", f"[{preview_vals}, ...]")
            
            console.print(embed_table)
        else:
            console.print("[yellow]No embeddings generated.[/yellow]")
        
        console.print("\n[bold green]Visualization complete.[/bold green]")
        
    except ImportError:
        console.print("[red]langchain-oracledb is required for Oracle AI visualization.[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Visualization error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        if conn:
            try: conn.close()
            except: pass
        if client:
            try: client.close()
            except: pass


if __name__ == "__main__":
    app()
