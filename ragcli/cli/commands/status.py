"""Status monitoring commands for ragcli CLI."""

import typer
from rich import print as rprint
from ragcli.utils.status import get_overall_status, print_status
from ragcli.config.config_manager import load_config

app = typer.Typer()

@app.command()
def status(
    format: str = typer.Option("rich", "--format", help="Output format (rich, json)")
):
    """Check system status: DB, APIs, documents, vectors."""
    config = load_config()
    overall = get_overall_status(config)
    
    if format == "rich":
        print_status(overall)
    elif format == "json":
        import json
        rprint(json.dumps(overall, indent=2, default=str))
    else:
        rprint(typer.style("Unsupported format.", fg=typer.colors.RED))

if __name__ == "__main__":
    app()
