"""Database commands for ragcli CLI."""

import typer
from ragcli.config.config_manager import load_config
from ragcli.database.oracle_client import OracleClient

app = typer.Typer()

@app.command()
def init():
    """Initialize the database schemas and vector index."""
    try:
        config = load_config()
        client = OracleClient(config)
        client.init_db()
        client.close()
        typer.echo(typer.style("Database initialized successfully!", fg=typer.colors.GREEN))
    except Exception as e:
        typer.echo(typer.style(f"Failed to initialize database: {e}", fg=typer.colors.RED))
        raise

if __name__ == "__main__":
    app()
