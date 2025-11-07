"""Dashboard UI component for ragcli."""

import gradio as gr
from ragcli.config.config_manager import load_config
from ragcli.database.oracle_client import OracleClient
from ragcli.utils.status import get_overall_status

def get_dashboard_stats(config):
    """Get stats for dashboard."""
    status = get_overall_status(config)
    docs_stats = status['documents']
    
    # Recent queries (last 5)
    client = OracleClient(config)
    conn = client.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT query_text, created_at FROM QUERIES 
        ORDER BY created_at DESC FETCH FIRST 5 ROWS ONLY
    """)
    recent_queries = cursor.fetchall()
    client.close()
    
    return docs_stats, status, recent_queries

def dashboard_ui(config):
    """Dashboard tab content."""
    docs_stats, status, recent_queries = get_dashboard_stats(config)
    
    gr.Markdown("# Dashboard")
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("### Quick Stats")
            total_docs_num = gr.Number(label="Total Documents", value=docs_stats['documents'])
            total_vectors_num = gr.Number(label="Total Vectors", value=docs_stats['vectors'])
            total_tokens_num = gr.Number(label="Total Tokens", value=docs_stats['total_tokens'])
        
        with gr.Column():
            gr.Markdown("### System Health")
            db_status_md = gr.Markdown(f"**Database**: {status['database']['status'].upper()} - {status['database']['message']}")
            ollama_status_md = gr.Markdown(f"**Ollama**: {status['ollama']['status'].upper()}")
            vllm_status_md = gr.Markdown(f"**vLLM**: {status['vllm']['status'].upper()}")
            overall_health_md = gr.Markdown(f"**Overall**: {'Healthy' if status['healthy'] else 'Issues'}")
    
    gr.Markdown("### Recent Queries")
    recent_list_md = gr.Markdown("\n".join([f"- {q[0]} ({q[1]})" for q in recent_queries]) if recent_queries else "No queries yet. Run some asks!")
    
    refresh_btn = gr.Button("Refresh")
    
    def refresh_stats():
        new_docs, new_status, new_recent = get_dashboard_stats(config)
        return (
            new_docs['documents'],
            new_docs['vectors'],
            new_docs['total_tokens'],
            f"**Database**: {new_status['database']['status'].upper()} - {new_status['database']['message']}",
            f"**Ollama**: {new_status['ollama']['status'].upper()}",
            f"**vLLM**: {new_status['vllm']['status'].upper()}",
            f"**Overall**: {'Healthy' if new_status['healthy'] else 'Issues'}",
            "\n".join([f"- {q[0]} ({q[1]})" for q in new_recent]) if new_recent else "No queries yet."
        )
    
    refresh_btn.click(
        refresh_stats,
        outputs=[
            total_docs_num,
            total_vectors_num,
            total_tokens_num,
            db_status_md,
            ollama_status_md,
            vllm_status_md,
            overall_health_md,
            recent_list_md
        ]
    )
    
    # Quick actions
    with gr.Row():
        gr.Button("Upload Document", variant="secondary")
        gr.Button("Ask Question", variant="secondary")
        gr.Button("View Documents", variant="secondary")
    
    gr.Markdown("**Automated monitoring: Refresh to check connections, counts, and health. Use `ragcli status` for CLI details.**")
