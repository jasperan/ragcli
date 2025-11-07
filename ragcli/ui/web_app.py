"""Web UI for ragcli using Gradio."""

import gradio as gr
from .styles import get_theme
from .components.dashboard import dashboard_ui
from .components.upload_panel import upload_ui
from .components.query_panel import query_ui
from .components.documents_panel import documents_ui
from .components.visualize_panel import visualize_ui
from .components.settings import settings_ui
from ragcli.config.config_manager import load_config

theme, css = get_theme()

def launch_web(host: str = "0.0.0.0", port: int = 7860, share: bool = False, auto_reload: bool = True):
    """Launch the Gradio web app."""
    config = load_config()
    
    with gr.Blocks(theme=theme, css=css, title="ragcli - Oracle DB 26ai RAG") as interface:
        gr.Markdown("# ragcli - Oracle DB 26ai RAG Interface")
        
        with gr.Tabs():
            with gr.TabItem("Dashboard"):
                dashboard_ui(config)
            with gr.TabItem("Upload"):
                upload_ui(config)
            with gr.TabItem("Ask"):
                query_ui(config)
            with gr.TabItem("Documents"):
                documents_ui(config)
            with gr.TabItem("Visualize"):
                visualize_ui(config)
            with gr.TabItem("Settings"):
                settings_ui(config)
        
        interface.queue(concurrency_count=1, max_size=100)
    
    interface.launch(
        server_name=host,
        server_port=port,
        share=share,
        inbrowser=True if auto_reload else False,
        show_error=True
    )

if __name__ == "__main__":
    launch_web()
