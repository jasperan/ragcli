import { useEffect, useState, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import type Graph from 'graphology';
import { ArrowLeft, Network } from 'lucide-react';
import { useGraphData } from '../hooks/useGraphData';
import type { GraphFilters } from '../hooks/useGraphData';
import { buildGraph } from '../lib/graph-adapter';
import { GraphCanvas } from '../components/graph/GraphCanvas';
import type { GraphCanvasHandle } from '../components/graph/GraphCanvas';
import { FilterPanel } from '../components/graph/FilterPanel';
import { GraphSearch } from '../components/graph/GraphSearch';
import { DocumentSelector } from '../components/graph/DocumentSelector';
import { NodeInfoBar } from '../components/graph/NodeInfoBar';

export function Visualizer() {
  const { data, loading, error, filters, setFilters, fetchGraph, fetchQueryGraph } = useGraphData();
  const [graph, setGraph] = useState<Graph | null>(null);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<{
    id: string;
    data: Record<string, any>;
  } | null>(null);
  const graphCanvasRef = useRef<GraphCanvasHandle>(null);

  useEffect(() => {
    fetchGraph();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (data && data.nodes.length > 0) {
      const g = buildGraph(data);
      setGraph(g);
    } else {
      setGraph(null);
    }
  }, [data]);

  const handleFilterApply = (newFilters: Partial<GraphFilters>) => {
    setFilters((prev: GraphFilters) => ({ ...prev, ...newFilters }));
    fetchGraph(newFilters);
  };

  const handleSearch = (query: string) => {
    fetchQueryGraph(query);
  };

  const handleFocusNode = useCallback((nodeId: string) => {
    graphCanvasRef.current?.focusNode(nodeId);
  }, []);

  return (
    <div className="flex h-[calc(100vh-3.5rem)] min-h-0 flex-col bg-paper">
      {/* Top bar */}
      <div className="flex h-12 shrink-0 items-center gap-4 border-b border-paper-line px-6">
        <Link
          to="/"
          className="flex items-center gap-2 text-[13px] text-ink-secondary transition-colors duration-150 hover:text-ink"
        >
          <ArrowLeft size={16} strokeWidth={1.5} className="text-ink-muted" />
          Back
        </Link>
        <div className="h-4 w-px bg-paper-line" />
        <h1 className="flex items-center gap-2 text-[13px] font-medium text-ink">
          <Network size={16} strokeWidth={1.5} className="text-ink-muted" />
          Embedding graph
        </h1>

        <div className="ml-auto flex items-center gap-4 font-mono text-[11px] tnum text-ink-muted">
          {data && (
            <>
              <span>{data.metadata.returned_chunks} nodes</span>
              <span>{data.edges.length} edges</span>
              <span>{data.metadata.embedding_model}</span>
              <span>{data.metadata.dimension}d</span>
            </>
          )}
        </div>
        <GraphSearch onSearch={handleSearch} loading={loading} />
      </div>

      {/* Rails: documents | graph | filters + inspector */}
      <div className="grid min-h-0 flex-1 grid-cols-[280px_minmax(0,1fr)_320px]">
        <aside className="min-h-0 overflow-y-auto border-r border-paper-line px-4 py-4">
          <DocumentSelector
            data={data}
            selectedDocumentId={selectedDocumentId}
            onSelectDocument={setSelectedDocumentId}
            onFocusNode={handleFocusNode}
          />
        </aside>

        <div className="relative min-h-0">
          {error && (
            <div className="absolute inset-0 z-30 flex items-center justify-center">
              <div className="max-w-md rounded-[10px] border border-wax/30 bg-wax-soft px-5 py-4">
                <p className="font-mono text-[11px] leading-5 text-wax-dim">{error}</p>
                <button
                  onClick={() => fetchGraph()}
                  className="mt-2 text-[12px] font-medium text-wax transition-colors duration-150 hover:text-wax-dim"
                >
                  Try again
                </button>
              </div>
            </div>
          )}

          {loading && !graph && (
            <div className="absolute inset-0 z-30 flex items-center justify-center">
              <div className="flex items-center gap-3">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-ink-muted border-t-transparent" />
                <span className="font-mono text-[11px] text-ink-muted">Loading embedding graph</span>
              </div>
            </div>
          )}

          {graph && (
            <GraphCanvas
              ref={graphCanvasRef}
              graph={graph}
              highlightedDocumentId={selectedDocumentId}
              onNodeSelect={(id, nodeData) =>
                setSelectedNode(id && nodeData ? { id, data: nodeData } : null)
              }
            />
          )}

          {!loading && !error && data && data.nodes.length === 0 && (
            <div className="absolute inset-0 z-30 flex flex-col items-center justify-center text-center">
              <Network size={18} strokeWidth={1.5} className="mb-2 text-ink-muted" />
              <p className="text-[13px] text-ink">No embeddings found</p>
              <p className="mt-1 font-mono text-[11px] text-ink-muted">
                Add a document on the home page, then come back.
              </p>
            </div>
          )}
        </div>

        <aside className="min-h-0 space-y-5 overflow-y-auto border-l border-paper-line px-4 py-4">
          <FilterPanel filters={filters} onApply={handleFilterApply} loading={loading} />
          <div className="border-t border-paper-line pt-4">
            {selectedNode ? (
              <NodeInfoBar key={selectedNode.id} nodeData={selectedNode.data} onFocus={() => handleFocusNode(selectedNode.id)} />
            ) : (
              <div>
                <h2 className="text-[13px] font-medium text-ink">Selection</h2>
                <p className="mt-2 text-[12px] leading-5 text-ink-secondary">
                  Select a node to read its chunk, token count and best similarity.
                </p>
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
