import { useRef, useImperativeHandle, forwardRef, useEffect } from 'react';
import type Graph from 'graphology';
import { useSigma } from '../../hooks/useSigma';
import { GraphControls } from './GraphControls';

export interface GraphCanvasHandle {
  focusNode: (nodeId: string) => void;
}

interface GraphCanvasProps {
  graph: Graph | null;
  highlightedDocumentId?: string | null;
  onNodeSelect?: (nodeId: string | null, nodeData: Record<string, any> | null) => void;
}

export const GraphCanvas = forwardRef<GraphCanvasHandle, GraphCanvasProps>(function GraphCanvas(
  { graph, highlightedDocumentId, onNodeSelect },
  ref,
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { state, zoomIn, zoomOut, resetCamera, focusNode, toggleLayout } = useSigma(
    containerRef,
    graph,
    { highlightedDocumentId },
  );

  useImperativeHandle(ref, () => ({ focusNode }), [focusNode]);

  const selectedNodeData = state.selectedNode && graph?.hasNode(state.selectedNode)
    ? graph.getNodeAttributes(state.selectedNode)
    : null;

  const hoveredNodeData = state.hoveredNode && graph?.hasNode(state.hoveredNode)
    ? graph.getNodeAttributes(state.hoveredNode)
    : null;

  useEffect(() => {
    onNodeSelect?.(state.selectedNode, selectedNodeData ?? null);
  }, [state.selectedNode, selectedNodeData, onNodeSelect]);

  return (
    <div className="relative h-full w-full">
      <div
        ref={containerRef}
        className="h-full w-full bg-paper"
        style={{ cursor: 'default' }}
      />

      {hoveredNodeData && !state.selectedNode && (
        <div className="pointer-events-none absolute left-4 top-4 z-10 max-w-sm rounded-[8px] border border-paper-line bg-paper-card px-3 py-2">
          <p className="truncate text-[12px] font-medium text-ink">
            {hoveredNodeData.nodeType === 'query' ? 'Query' : hoveredNodeData.documentName}
            {hoveredNodeData.nodeType !== 'query' && ` #${hoveredNodeData.chunkNumber}`}
          </p>
          <p className="mt-1 line-clamp-2 text-[11px] leading-5 text-ink-secondary">{hoveredNodeData.textPreview}</p>
        </div>
      )}

      <GraphControls
        onZoomIn={zoomIn}
        onZoomOut={zoomOut}
        onReset={resetCamera}
        onToggleLayout={toggleLayout}
        layoutRunning={state.layoutRunning}
      />
    </div>
  );
});
