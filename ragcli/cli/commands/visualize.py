"""Visualization commands for ragcli CLI."""

import typer
from rich.console import Console
from rich.panel import Panel
from rich import print as rprint
from ragcli.core.rag_engine import ask_query
from ragcli.config.config_manager import load_config
from ragcli.visualization.retrieval_chain import show_retrieval_chain  # TODO
# from ragcli.visualization.similarity_heatmap import show_heatmap  # TODO
from typing import Optional

app = typer.Typer()
console = Console()

@app.command()
def visualize(
    query_id: Optional[str] = None,
    query: Optional[str] = None,
    type: str = typer.Option("chain", "--type", "-t", help="Visualization type (chain, embedding, heatmap)")
):
    """Visualize retrieval chain or embedding space for a query."""
    config = load_config()
    
    if query:
        # Run query and visualize
        result = ask_query(query, config=config, show_chain=True)  # Assume show_chain triggers viz
        if type == "chain":
            # TODO: Use show_retrieval_chain(result)
            panel = Panel("Retrieval Chain Visualization\n[Query] -> [Embedding] -> [Search] -> [Context] -> [LLM]\nDetails: ...\n", title="RAG Pipeline")
            console.print(panel)
        elif type == "heatmap":
            # TODO: show_heatmap
            rprint("Similarity Heatmap (stub)")
        else:
            rprint("Embedding Space (stub)")
    elif query_id:
        # TODO: Fetch from QUERIES table
        rprint(f"Visualizing query {query_id} (stub)")
    else:
        rprint("Provide --query or query_id")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()
