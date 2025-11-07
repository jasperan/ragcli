"""Upload commands for ragcli CLI."""

import typer
from pathlib import Path
from rich.progress import Progress
from ragcli.core.rag_engine import upload_document
from ragcli.config.config_manager import load_config

app = typer.Typer()

@app.command()
def upload(
    file_path: str,
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Upload directory recursively"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output")
):
    """Upload document(s) to the vector store."""
    config = load_config()
    
    path = Path(file_path)
    if not path.exists():
        typer.echo(typer.style("File or directory not found.", fg=typer.colors.RED))
        raise typer.Exit(1)
    
    if path.is_dir() and recursive:
        # TODO: Walk directory, upload each file
        files = list(path.rglob("*"))
        files = [f for f in files if f.is_file() and f.suffix.lstrip('.') in config['documents']['supported_formats']]
        
        with Progress() as progress:
            task = progress.add_task("Uploading...", total=len(files))
            for file in files:
                try:
                    metadata = upload_document(str(file), config)
                    if verbose:
                        typer.echo(f"Uploaded {file.name}: {metadata['document_id']}")
                except Exception as e:
                    typer.echo(typer.style(f"Failed to upload {file.name}: {e}", fg=typer.colors.RED))
                progress.advance(task)
    else:
        if path.is_dir():
            typer.echo("Use --recursive for directories.")
            raise typer.Exit(1)
        
        try:
            metadata = upload_document(str(path), config)
            typer.echo(typer.style("Upload successful!", fg=typer.colors.GREEN))
            typer.echo(f"Document ID: {metadata['document_id']}")
            typer.echo(f"Chunks: {metadata['chunk_count']}, Tokens: {metadata['total_tokens']}")
            if verbose:
                for k, v in metadata.items():
                    typer.echo(f"{k}: {v}")
        except Exception as e:
            typer.echo(typer.style(f"Upload failed: {e}", fg=typer.colors.RED))
            raise typer.Exit(1)

if __name__ == "__main__":
    app()
