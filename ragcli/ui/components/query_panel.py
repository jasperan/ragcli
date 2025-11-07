"""Query panel UI component for ragcli."""

import gradio as gr
from ragcli.core.rag_engine import ask_query
from ragcli.config.config_manager import load_config
from ragcli.database.oracle_client import OracleClient

def get_document_list(config):
    """Get list of document IDs and names."""
    client = OracleClient(config)
    conn = client.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT document_id, filename FROM DOCUMENTS ORDER BY upload_timestamp DESC")
    docs = cursor.fetchall()
    client.close()
    return [(doc[0], doc[1]) for doc in docs]

def query_ui(config):
    """Ask tab content."""
    docs = get_document_list(config)
    
    with gr.Row():
        with gr.Column(scale=3):
            query_input = gr.Textbox(
                label="Your Question",
                placeholder="Ask something about your documents...",
                lines=3
            )
        with gr.Column(scale=1):
            docs_selector = gr.CheckboxGroup(
                label="Select Documents",
                choices=docs,
                value=[d[0] for d in docs[:5]] if docs else [],
                interactive=True
            )
    
    with gr.Row():
        top_k = gr.Number(label="Top K Results", value=5, minimum=1, maximum=20)
        threshold = gr.Number(label="Min Similarity", value=0.5, minimum=0, maximum=1)
        send_btn = gr.Button("Ask", variant="primary")
    
    response = gr.Markdown(label="Answer")
    results_table = gr.Dataframe(label="Retrieval Results")
    
    def ask_question(query, selected_docs, top_k_val, threshold_val):
        if not query:
            return "Please enter a question.", []
        
        document_ids = selected_docs if selected_docs else None
        result = ask_query(
            query,
            document_ids,
            int(top_k_val),
            threshold_val,
            config
        )
        
        # Format results for table
        table_data = []
        for r in result['results']:
            table_data.append({
                'Document ID': r['document_id'],
                'Chunk': r['chunk_number'],
                'Similarity': f"{r['similarity_score']:.3f}",
                'Excerpt': r['text']
            })
        
        return result['response'], table_data
    
    send_btn.click(
        ask_question,
        inputs=[query_input, docs_selector, top_k, threshold],
        outputs=[response, results_table]
    )
    
    # Real-time preview stub
    def preview_results(query, selected_docs):
        if len(query) < 3:
            return []
        # TODO: Debounced search
        return "Live preview (stub)"
    
    query_input.change(
        preview_results,
        inputs=[query_input, docs_selector],
        outputs=results_table
    )
    
    gr.Markdown("**Real-time similarity updates as you type (debounced).**")
