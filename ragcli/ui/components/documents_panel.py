"""Documents panel UI component for ragcli."""

import gradio as gr
from ragcli.config.config_manager import load_config
from ragcli.database.oracle_client import OracleClient
from ragcli.database.vector_ops import generate_id  # Not used, for example

def get_documents_data(config):
    """Get documents data for table."""
    client = OracleClient(config)
    conn = client.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT document_id, filename, file_format, upload_timestamp, 
               chunk_count, total_tokens, approximate_embedding_size_bytes
        FROM DOCUMENTS ORDER BY upload_timestamp DESC
    """)
    rows = cursor.fetchall()
    client.close()
    
    headers = ['ID', 'Filename', 'Format', 'Uploaded', 'Chunks', 'Tokens', 'Embedding Size (bytes)']
    data = []
    for row in rows:
        data.append([
            row[0],
            row[1],
            row[2],
            str(row[3]),
            str(row[4]),
            str(row[5]),
            str(row[6])
        ])
    return headers, data

def delete_document(doc_id, config):
    """Delete a document."""
    if not doc_id:
        return "No document selected."
    
    client = OracleClient(config)
    conn = client.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM DOCUMENTS WHERE document_id = :doc_id", {'doc_id': doc_id})
        conn.commit()
        if cursor.rowcount > 0:
            return f"Deleted document {doc_id}."
        else:
            return "Document not found."
    except Exception as e:
        conn.rollback()
        return f"Delete failed: {str(e)}"
    finally:
        client.close()

def documents_ui(config):
    """Documents tab content."""
    with gr.Row():
        refresh_btn = gr.Button("Refresh List", variant="secondary")
    
    with gr.Row():
        docs_table = gr.Dataframe(
            label="Uploaded Documents",
            headers=get_documents_data(config)[0],
            datatype=["str", "str", "str", "str", "number", "number", "number"],
            interactive=False
        )
    
    with gr.Row():
        delete_btn = gr.Button("Delete Selected", variant="stop")
    
    status = gr.Markdown()
    
    def refresh_documents():
        headers, data = get_documents_data(config)
        return gr.update(headers=headers, value=data)
    
    refresh_btn.click(
        refresh_documents,
        outputs=docs_table
    )
    
    def delete_selected(selected):
        if selected:
            doc_id = selected[0][0]  # First column ID
            msg = delete_document(doc_id, config)
            refresh_documents()  # Refresh after delete
            return msg, gr.update()
        return "Select a row to delete.", gr.update()
    
    delete_btn.click(
        delete_selected,
        inputs=docs_table,
        outputs=[status, docs_table]
    )
    
    # Search stub
    search_input = gr.Textbox(label="Search by name", placeholder="Filter documents...")
    def filter_docs(search):
        # TODO: Implement filter
        return get_documents_data(config)
    
    search_input.change(
        filter_docs,
        inputs=search_input,
        outputs=docs_table
    )
    
    gr.Markdown("**Select a row and click Delete to remove a document. Bulk actions coming soon.**")
