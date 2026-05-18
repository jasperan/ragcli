"""First-run diagnostics for ragcli."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import requests
import typer
from rich.console import Console
from rich.table import Table

from ragcli.config.config_manager import load_config

console = Console()


def parse_dsn_host_port(dsn: str) -> tuple[Optional[str], Optional[int]]:
    """Best-effort host/port extraction for common Oracle DSN forms."""
    if not dsn:
        return None, None

    dsn = dsn.strip()
    if dsn.startswith("("):
        return None, None

    if "://" in dsn:
        parsed = urlparse(dsn)
        return parsed.hostname, parsed.port

    host_port = dsn.split("/", 1)[0]
    if ":" not in host_port:
        return host_port or None, 1521

    host, port_str = host_port.rsplit(":", 1)
    try:
        return host or None, int(port_str)
    except ValueError:
        return host or None, None


def _socket_reachable(host: str, port: int, timeout: float = 2.0) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"{host}:{port} accepts TCP connections"
    except OSError as exc:
        return False, f"{host}:{port} is not reachable: {exc}"


def _port_status(port: int) -> tuple[str, str]:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        in_use = sock.connect_ex(("127.0.0.1", port)) == 0
    if in_use:
        return "warn", f"localhost:{port} is already in use"
    return "ok", f"localhost:{port} is available"


def _status_label(status: str) -> str:
    if status == "ok":
        return "[green]ok[/green]"
    if status == "warn":
        return "[yellow]warn[/yellow]"
    return "[red]fail[/red]"


def _add_row(rows: list[dict[str, str]], component: str, status: str, detail: str, action: str = "") -> None:
    rows.append({
        "component": component,
        "status": status,
        "detail": detail,
        "action": action,
    })


def _load_config_row(rows: list[dict[str, str]]) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    config_path = Path("config.yaml")
    example_path = Path("config.yaml.example")
    if config_path.exists():
        detail = "config.yaml found"
    elif example_path.exists():
        detail = "config.yaml missing; using config.yaml.example defaults"
    else:
        _add_row(rows, "config", "fail", "No config.yaml or config.yaml.example found", "Run from the project root or create config.yaml")
        return None, None

    try:
        config = load_config()
    except Exception as exc:
        _add_row(rows, "config", "fail", f"{detail}; load failed: {exc}", "Fix config.yaml and rerun ragcli doctor")
        return None, None

    _add_row(rows, "config", "ok" if config_path.exists() else "warn", detail, "Copy config.yaml.example to config.yaml for local overrides" if not config_path.exists() else "")
    return config, str(config_path if config_path.exists() else example_path)


def _check_ollama(rows: list[dict[str, str]], config: dict[str, Any]) -> None:
    ollama = config.get("ollama", {})
    endpoint = str(ollama.get("endpoint", "http://localhost:11434")).rstrip("/")
    try:
        response = requests.get(f"{endpoint}/api/tags", timeout=2)
        response.raise_for_status()
        models = response.json().get("models", [])
    except Exception as exc:
        _add_row(rows, "ollama", "fail", f"{endpoint} is not reachable: {exc}", "Start Ollama with `ollama serve`")
        return

    names = {model.get("name") for model in models if isinstance(model, dict)}
    _add_row(rows, "ollama", "ok", f"{endpoint} returned {len(names)} model(s)")

    for key, label in (("embedding_model", "embedding model"), ("chat_model", "chat model")):
        configured = ollama.get(key)
        if not configured:
            _add_row(rows, label, "warn", f"ollama.{key} is not configured", f"Set ollama.{key} in config.yaml")
        elif configured in names or f"{configured}:latest" in names:
            _add_row(rows, label, "ok", f"{configured} is installed")
        else:
            _add_row(rows, label, "warn", f"{configured} not found in Ollama", f"Run `ollama pull {configured}`")


def _resolve_oracle_config(config: dict[str, Any]) -> tuple[dict[str, Any], str]:
    database = config.get("database", {})
    profiles = database.get("profiles")
    if isinstance(profiles, dict):
        active_profile = database.get("active_profile", "local")
        profile = profiles.get(active_profile)
        if isinstance(profile, dict):
            return profile, f"database.profiles.{active_profile}"
    return config.get("oracle", {}), "oracle"


def _check_oracle(rows: list[dict[str, str]], config: dict[str, Any]) -> None:
    oracle, source = _resolve_oracle_config(config)
    dsn = str(oracle.get("dsn", ""))
    host, port = parse_dsn_host_port(dsn)
    if not host or not port:
        _add_row(rows, "oracle", "warn", f"Could not parse Oracle DSN `{dsn}` from {source}", "Verify Oracle DSN in config.yaml")
        return

    ok, detail = _socket_reachable(host, port)
    _add_row(rows, "oracle port", "ok" if ok else "fail", detail, "Start Oracle or update Oracle DSN" if not ok else "")
    if not ok:
        return

    username = str(oracle.get("username") or oracle.get("user") or "")
    password = str(oracle.get("password") or "")
    if not username:
        _add_row(rows, "oracle auth", "fail", f"No Oracle username configured in {source}", "Set ORACLE_USERNAME or update config.yaml")
        return
    if not password or password.startswith("${"):
        _add_row(rows, "oracle auth", "warn", f"Oracle password is not resolved in {source}", "Set ORACLE_PASSWORD and rerun ragcli doctor")
        return

    try:
        import oracledb
    except Exception as exc:
        _add_row(rows, "oracle auth", "warn", f"python-oracledb is unavailable: {exc}", "Install ragcli runtime dependencies")
        return

    params: dict[str, Any] = {}
    if oracle.get("use_tls") and oracle.get("tls_wallet_path"):
        params["wallet_location"] = oracle["tls_wallet_path"]

    try:
        conn = oracledb.connect(user=username, password=password, dsn=dsn, **params)
        try:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT 1 FROM DUAL")
                cursor.fetchone()
            finally:
                cursor.close()
        finally:
            conn.close()
    except Exception as exc:
        _add_row(rows, "oracle auth", "fail", f"{username}@{dsn} failed from {source}: {exc}", "Check ORACLE_USERNAME, ORACLE_PASSWORD, and ORACLE_DSN")
        return

    _add_row(rows, "oracle auth", "ok", f"{username}@{dsn} connected from {source}")


def _check_docker(rows: list[dict[str, str]]) -> None:
    docker = shutil.which("docker")
    if not docker:
        _add_row(rows, "docker", "warn", "Docker CLI not found", "Install Docker if using docker compose")
        return

    try:
        result = subprocess.run(
            [docker, "compose", "version"],
            check=False,
            text=True,
            capture_output=True,
            timeout=3,
        )
    except Exception as exc:
        _add_row(rows, "docker", "warn", f"Docker found but compose check failed: {exc}")
        return

    if result.returncode == 0:
        _add_row(rows, "docker", "ok", result.stdout.strip())
    else:
        _add_row(rows, "docker", "warn", result.stderr.strip() or "docker compose is unavailable")


def _ragcli_executable() -> Optional[str]:
    executable = shutil.which("ragcli")
    if executable:
        return executable

    invoked = Path(sys.argv[0])
    if invoked.name == "ragcli" and invoked.exists():
        return str(invoked.resolve())

    return None


def doctor(json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON")) -> None:
    """Check install, configuration, local services, and next actions."""
    rows: list[dict[str, str]] = []

    py_ok = sys.version_info >= (3, 9)
    _add_row(
        rows,
        "python",
        "ok" if py_ok else "fail",
        f"{platform.python_version()} at {sys.executable}",
        "Use Python 3.9 or newer" if not py_ok else "",
    )

    try:
        version = importlib.metadata.version("oracle-ragcli")
        _add_row(rows, "package", "ok", f"oracle-ragcli {version}")
    except importlib.metadata.PackageNotFoundError:
        _add_row(rows, "package", "warn", "oracle-ragcli is not installed as a package", "Run `python -m pip install -e .`")

    executable = _ragcli_executable()
    _add_row(rows, "cli", "ok" if executable else "fail", executable or "`ragcli` is not on PATH", "Install with `python -m pip install -e .`" if not executable else "")

    config, _ = _load_config_row(rows)
    if config:
        api_port = int(config.get("api", {}).get("port", 8000))
        status, detail = _port_status(api_port)
        _add_row(rows, "api port", status, detail, "Set api.port or stop the process using the port" if status == "warn" else "")
        _check_oracle(rows, config)
        _check_ollama(rows, config)

    _check_docker(rows)

    if json_output:
        sys.stdout.write(json.dumps(rows, indent=2) + "\n")
        return

    table = Table(title="ragcli doctor")
    table.add_column("Component", style="bold")
    table.add_column("Status")
    table.add_column("Details")
    table.add_column("Next action")
    for row in rows:
        table.add_row(row["component"], _status_label(row["status"]), row["detail"], row["action"])
    console.print(table)
