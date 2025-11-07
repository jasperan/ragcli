"""Upload panel UI component for ragcli."""

import gradio as gr
from ragcli.core.rag_engine import upload_document
from ragcli.config.config_manager import load_config

def upload_ui(config):
    """Upload tab content."""
    with gr.Row():
        file_input = gr.File(
            label="Upload Document (TXT, MD, PDF)",
            file_types=[".txt", ".md", ".pdf"],
            file_count="single"
        )
    
    with gr.Row():
        upload_btn = gr.Button("Upload", variant="primary")
    
    output = gr.JSON(label="Upload Result")
    status = gr.Markdown()
    
    def upload_file(file):
        if not file:
            return "No file selected.", {}
        
        try:
            metadata = upload_document(file.name, config)
            status_text = f"Uploaded successfully! ID: {metadata['document_id']}"
            return status_text, metadata
        except Exception as e:
            status_text = f"Upload failed: {str(e)}"
            return status_text, {}
    
    upload_btn.click(
        upload_file,
        inputs=file_input,
        outputs=[status, output]
    )
    
    # OCR note
    gr.Markdown("*PDFs will be processed with OCR via DeepSeek-OCR if enabled in config.*")
