"""Status monitoring commands for ragcli CLI."""

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from ragcli.utils.status import get_overall_status, print_status, get_vector_statistics, get_index_metadata
from ragcli.config.config_manager import load_config

app = typer.Typer()
console = Console()

@app.command()
def status(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed vector statistics"),
    format: str = typer.Option("rich", "--format", help="Output format (rich, json)")
):
    """Check system status: DB, APIs, documents, vectors."""
    config = load_config()
    overall = get_overall_status(config)
    
    if format == "json":
        import json
        if verbose:
            overall['vector_stats'] = get_vector_statistics(config)
            overall['index_metadata'] = get_index_metadata(config)
        rprint(json.dumps(overall, indent=2, default=str))
        return
    
    # Rich format
    if not verbose:
        print_status(overall)
        return
    
    # Verbose mode with detailed statistics
    print_status(overall)
    
    console.print("\n[bold cyan]═══ Vector Statistics ═══[/bold cyan]\n")
    
    # Get detailed stats
    vector_stats = get_vector_statistics(config)
    index_meta = get_index_metadata(config)
    
    # Vector Configuration Table
    config_table = Table(title="Vector Configuration", show_header=True)
    config_table.add_column("Parameter", style="cyan")
    config_table.add_column("Value", style="yellow")
    
    config_table.add_row("Embedding Dimension", str(vector_stats.get('dimension', 'N/A')))
    config_table.add_row("Index Type", vector_stats.get('index_type', 'N/A'))
    config_table.add_row("Embedding Model", config['ollama']['embedding_model'])
    config_table.add_row("HNSW M Parameter", str(config.get('vector_index', {}).get('m', 'N/A')))
    config_table.add_row("HNSW EF Construction", str(config.get('vector_index', {}).get('ef_construction', 'N/A')))
    
    console.print(config_table)
    console.print()
    
    # Storage Statistics
    storage_table = Table(title="Storage Statistics", show_header=True)
    storage_table.add_column("Metric", style="cyan")
    storage_table.add_column("Value", style="yellow")
    
    total_vectors = vector_stats.get('total_vectors', 0)
    dimension = vector_stats.get('dimension', 768)
    vector_size_mb = (total_vectors * dimension * 4) / (1024 * 1024)  # 4 bytes per float
    
    storage_table.add_row("Total Vectors", f"{total_vectors:,}")
    storage_table.add_row("Estimated Vector Size", f"{vector_size_mb:.2f} MB")
    storage_table.add_row("Total Documents", f"{vector_stats.get('total_documents', 0):,}")
    storage_table.add_row("Total Tokens", f"{vector_stats.get('total_tokens', 0):,}")
    storage_table.add_row("Avg Chunks per Doc", f"{vector_stats.get('avg_chunks_per_doc', 0):.1f}")
    
    console.print(storage_table)
    console.print()
    
    # Index Metadata
    if index_meta.get('indexes'):
        index_table = Table(title="Vector Indexes", show_header=True)
        index_table.add_column("Index Name", style="cyan")
        index_table.add_column("Table", style="magenta")
        index_table.add_column("Column", style="yellow")
        index_table.add_column("Status", style="green")
        
        for idx in index_meta['indexes']:
            index_table.add_row(
                idx['index_name'],
                idx['table_name'],
                idx['column_name'],
                idx['status']
            )
        
        console.print(index_table)
        console.print()
    
    # Performance Metrics
    perf_table = Table(title="Performance Metrics", show_header=True)
    perf_table.add_column("Metric", style="cyan")
    perf_table.add_column("Value", style="yellow")
    
    perf_table.add_row("Avg Search Latency", f"{vector_stats.get('avg_search_latency_ms', 0):.2f} ms")
    perf_table.add_row("Cache Hit Rate", f"{vector_stats.get('cache_hit_rate', 0):.1f}%")
    
    console.print(perf_table)
    
    # Recommendations
    recommendations = []
    if total_vectors > 100000 and vector_stats.get('index_type') != 'HYBRID':
        recommendations.append("Consider using HYBRID index for better performance with large datasets")
    if vector_stats.get('avg_chunks_per_doc', 0) > 50:
        recommendations.append("Documents have many chunks - consider increasing chunk_size in config")
    
    if recommendations:
        console.print("\n[bold yellow]💡 Recommendations:[/bold yellow]")
        for rec in recommendations:
            console.print(f"  • {rec}")

if __name__ == "__main__":
    app()
