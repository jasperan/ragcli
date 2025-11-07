"""Visualize panel UI component for ragcli."""

import gradio as gr
from ragcli.core.rag_engine import ask_query
from ragcli.config.config_manager import load_config
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from ragcli.visualization.embedding_space import project_embeddings  # TODO
from ragcli.visualization.retrieval_chain import create_chain_fig  # TODO
from ragcli.visualization.similarity_heatmap import create_heatmap  # TODO

def visualize_ui(config):
    """Visualize tab content."""
    with gr.Tabs():
        with gr.TabItem("Retrieval Chain"):
            query_input = gr.Textbox(label="Query for Chain Visualization", lines=2)
            viz_chain_btn = gr.Button("Generate Chain")
            chain_fig = gr.Plot(label="RAG Pipeline")
            
            def generate_chain(query):
                if not query:
                    return px.line(title="No query provided")
                
                # Run query to get result
                result = ask_query(query, config=config)
                
                # TODO: Use create_chain_fig(result)
                fig = make_subplots(rows=1, cols=1, subplot_titles=["RAG Retrieval Chain"])
                fig.add_trace(go.Scatter(x=[1,2,3,4], y=[1,2,3,4], mode='lines+markers', name='Pipeline Steps'), row=1, col=1)
                fig.update_layout(title="Retrieval Chain (Stub: Query -> Embed -> Search -> LLM)")
                return fig
            
            viz_chain_btn.click(generate_chain, inputs=query_input, outputs=chain_fig)
        
        with gr.TabItem("Embedding Space"):
            query_input_emb = gr.Textbox(label="Query for Embedding Projection", lines=2)
            viz_emb_btn = gr.Button("Project Embeddings")
            emb_fig = gr.Plot(label="3D Embedding Space")
            
            def generate_embedding_viz(query):
                if not query:
                    return px.scatter_3d(title="No query provided")
                
                # TODO: Fetch embeddings from DB, project with UMAP, color by similarity
                # Stub data
                np.random.seed(42)
                x, y, z = np.random.rand(50, 3).T
                fig = px.scatter_3d(x=x, y=y, z=z, title="Embedding Space (UMAP Projection, Stub)")
                fig.update_layout(scene=dict(xaxis_title="Dim1", yaxis_title="Dim2", zaxis_title="Dim3"))
                return fig
            
            viz_emb_btn.click(generate_embedding_viz, inputs=query_input_emb, outputs=emb_fig)
        
        with gr.TabItem("Similarity Heatmap"):
            query_input_heat = gr.Textbox(label="Query for Heatmap", lines=2)
            viz_heat_btn = gr.Button("Generate Heatmap")
            heat_fig = gr.Plot(label="Similarity Scores")
            
            def generate_heatmap(query):
                if not query:
                    return px.imshow(title="No query provided")
                
                # TODO: Get similarities from search
                # Stub
                data = np.random.rand(5, 5)
                fig = px.imshow(data, title="Similarity Heatmap (Stub)", color_continuous_scale="Blues")
                return fig
            
            viz_heat_btn.click(generate_heatmap, inputs=query_input_heat, outputs=heat_fig)
        
        with gr.TabItem("Metrics"):
            metrics_query = gr.Textbox(label="Query for Metrics", lines=2)
            metrics_btn = gr.Button("Show Metrics")
            metrics_table = gr.Dataframe(label="Query Metrics")
            
            def show_metrics(query):
                if not query:
                    return []
                
                result = ask_query(query, config=config)
                metrics_data = [{"Metric": k, "Value": v} for k, v in result['metrics'].items()]
                return metrics_data
            
            metrics_btn.click(show_metrics, inputs=metrics_query, outputs=metrics_table)
    
    gr.Markdown("""
    **Export visualizations**: Right-click on plots or use browser tools.
    **Full-screen**: Click on plot for interactive view.
    """)
