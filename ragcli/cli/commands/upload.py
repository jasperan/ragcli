"""Upload commands for ragcli CLI."""

import typer
from pathlib import Path
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn
from rich.console import Console
from rich.panel import Panel
from ragcli.core.rag_engine import upload_document_with_progress
from ragcli.config.config_manager import load_config

app = typer.Typer()
console = Console()

@app.command("add")
def add(
    file_path: str,
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Upload directory recursively"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output")
):
    """Upload document(s) to the vector store."""
    config = load_config()
    
    path = Path(file_path)
    if not path.exists():
        console.print("[red]File or directory not found.[/red]")
        raise typer.Exit(1)
    
    if path.is_dir() and recursive:
        # Walk directory, upload each file
        files = list(path.rglob("*"))
        files = [f for f in files if f.is_file() and f.suffix.lstrip('.') in config['documents']['supported_formats']]
        
        if not files:
            console.print("[yellow]No supported documents found in directory.[/yellow]")
            return
        
        console.print(f"[cyan]Found {len(files)} document(s) to upload[/cyan]\n")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            overall_task = progress.add_task(f"[cyan]Uploading files...", total=len(files))
            
            for file in files:
                try:
                    metadata = upload_document_with_progress(str(file), config, progress)
                    if verbose:
                        console.print(f"[green]✓[/green] {file.name}: {metadata['document_id']}")
                except Exception as e:
                    console.print(f"[red]✗[/red] {file.name}: {e}")
                progress.advance(overall_task)
        
        console.print("\n[bold green]Batch upload complete![/bold green]")
        
    else:
        if path.is_dir():
            console.print("[yellow]Use --recursive for directories.[/yellow]")
            raise typer.Exit(1)
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
                console=console
            ) as progress:
                metadata = upload_document_with_progress(str(path), config, progress)
            
            # Show success summary
            console.print("\n[bold green]✓ Upload successful![/bold green]")
            summary = f"""
Document ID: [cyan]{metadata['document_id']}[/cyan]
Filename: [cyan]{metadata['filename']}[/cyan]
Format: [cyan]{metadata['file_format'].upper()}[/cyan]
Size: [cyan]{metadata['file_size_bytes'] / 1024:.2f} KB[/cyan]
Chunks: [cyan]{metadata['chunk_count']}[/cyan]
Total Tokens: [cyan]{metadata['total_tokens']}[/cyan]
Upload Time: [cyan]{metadata['upload_time_ms']:.0f} ms[/cyan]
            """
            console.print(Panel(summary.strip(), title="Upload Summary", border_style="green"))
            
            if verbose:
                console.print("\n[bold]Full Metadata:[/bold]")
                for k, v in metadata.items():
                    console.print(f"  {k}: {v}")
                    
        except Exception as e:
            console.print(f"[bold red]✗ Upload failed:[/bold red] {e}")
            raise typer.Exit(1)

if __name__ == "__main__":
    app()
