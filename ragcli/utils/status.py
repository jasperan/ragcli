"""Status monitoring utilities for ragcli."""

import requests
from typing import Dict, Any
from ragcli.database.oracle_client import OracleClient
from ragcli.config.config_manager import load_config
from rich.console import Console

console = Console()

def check_db_connection(config: Dict[str, Any]) -> Dict[str, Any]:
    """Check Oracle DB connection."""
    try:
        client = OracleClient(config)
        conn = client.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM DUAL")
        result = cursor.fetchone()
        client.close()
        return {"status": "connected", "message": "Oracle DB connected successfully", "active_sessions": "N/A"}  # TODO: Query v$session
    except Exception as e:
        return {"status": "disconnected", "message": f"Oracle DB connection failed: {str(e)}", "active_sessions": 0}

def get_document_stats(config: Dict[str, Any]) -> Dict[str, Any]:
    """Get document and vector stats."""
    try:
        client = OracleClient(config)
        conn = client.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM DOCUMENTS")
        doc_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM CHUNKS")
        vector_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(total_tokens) FROM DOCUMENTS")
        total_tokens = cursor.fetchone()[0] or 0
        
        client.close()
        
        return {
            "status": "ok" if doc_count > 0 else "empty",
            "documents": doc_count,
            "vectors": vector_count,
            "total_tokens": total_tokens
        }
    except Exception as e:
        return {"status": "error", "documents": 0, "vectors": 0, "total_tokens": 0, "error": str(e)}

def check_ollama(config: Dict[str, Any]) -> Dict[str, Any]:
    """Check Ollama API."""
    try:
        endpoint = config['ollama']['endpoint']
        resp = requests.get(f"{endpoint}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = len(resp.json().get('models', []))
            return {"status": "connected", "message": f"Ollama connected ({models} models)"}
        else:
            return {"status": "error", "message": f"Ollama error {resp.status_code}"}
    except Exception as e:
        return {"status": "disconnected", "message": f"Ollama unreachable: {str(e)}"}

def check_vllm(config: Dict[str, Any]) -> Dict[str, Any]:
    """Check vLLM API for OCR."""
    try:
        endpoint = config['ocr']['vllm_endpoint']
        resp = requests.get(f"{endpoint}/health", timeout=5)
        if resp.status_code == 200:
            return {"status": "connected", "message": "vLLM connected"}
        else:
            return {"status": "error", "message": f"vLLM error {resp.status_code}"}
    except Exception as e:
        return {"status": "disconnected", "message": f"vLLM unreachable: {str(e)}"}

def get_overall_status(config: Dict[str, Any] = None) -> Dict[str, Any]:
    """Get comprehensive status."""
    if config is None:
        config = load_config()
    
    db = check_db_connection(config)
    stats = get_document_stats(config)
    ollama = check_ollama(config)
    vllm = check_vllm(config)
    
    overall = {
        "database": db,
        "documents": stats,
        "ollama": ollama,
        "vllm": vllm,
        "healthy": all(s["status"] in ["connected", "ok"] for s in [db, ollama, vllm])
    }
    
    return overall

def print_status(status: Dict[str, Any], rich_output: bool = True):
    """Print status in rich format."""
    if rich_output:
        from rich.table import Table
        table = Table(title="ragcli Status")
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Details")
        
        table.add_row("Database", status["database"]["status"], status["database"]["message"])
        table.add_row("Documents", status["documents"]["status"], f"{status['documents']['documents']} docs, {status['documents']['vectors']} vectors")
        table.add_row("Ollama", status["ollama"]["status"], status["ollama"]["message"])
        table.add_row("vLLM (OCR)", status["vllm"]["status"], status["vllm"]["message"])
        table.add_row("Overall", "healthy" if status["healthy"] else "issues", "All checks passed" if status["healthy"] else "Some issues detected")
        
        console.print(table)
    else:
        # For logs or JSON
        import json
        print(json.dumps(status, indent=2))
