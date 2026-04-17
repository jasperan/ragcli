"""Export commands for ragcli CLI."""

import json
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint

from ragcli.config.config_manager import load_config

app = typer.Typer()


@app.command()
def export(
    logs: bool = typer.Option(True, "--logs", help="Export logs"),
    format: str = typer.Option("json", "--format", help="Output format (json, csv)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file"),
) -> None:
    """Export session logs to a file or stdout."""
    if not logs:
        rprint("[yellow]Metrics export is not implemented yet.[/yellow]")
        raise typer.Exit(code=1)

    config = load_config()
    log_file = Path(config.get("logging", {}).get("file", "logs/ragcli.log"))
    if not log_file.exists():
        rprint(f"[red]Log file not found: {log_file}[/red]")
        raise typer.Exit(code=1)

    if format == "csv":
        rprint("[yellow]CSV export is not implemented yet.[/yellow]")
        raise typer.Exit(code=1)

    payload = log_file.read_text(encoding="utf-8")
    if format == "json":
        payload = json.dumps({"log_file": str(log_file), "content": payload}, indent=2)

    if output:
        Path(output).write_text(payload, encoding="utf-8")
        rprint(f"Exported to {output}")
    else:
        rprint(payload)

if __name__ == "__main__":
    app()
