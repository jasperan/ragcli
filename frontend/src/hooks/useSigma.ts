import { useEffect, useRef, useState, useCallback } from 'react';
import Sigma from 'sigma';
import Graph from 'graphology';
import EdgeCurveProgram from '@sigma/edge-curve';
import FA2Layout from 'graphology-layout-forceatlas2/worker';

function dimColor(hex: string, amount: number): string {
  const bg = { r: 0x06, g: 0x06, b: 0x0a };
  let r: number, g: number, b: number;
  if (hex.startsWith('rgb')) {
    const match = hex.match(/(\d+)/g);
    if (match) {
      r = parseInt(match[0]); g = parseInt(match[1]); b = parseInt(match[2]);
    } else {
      return hex;
    }
  } else {
    r = parseInt(hex.slice(1, 3), 16);
    g = parseInt(hex.slice(3, 5), 16);
    b = parseInt(hex.slice(5, 7), 16);
  }
  const nr = Math.round(r * amount + bg.r * (1 - amount));
  const ng = Math.round(g * amount + bg.g * (1 - amount));
  const nb = Math.round(b * amount + bg.b * (1 - amount));
  return `rgb(${nr},${ng},${nb})`;
}

export interface SigmaState {
  selectedNode: string | null;
  hoveredNode: string | null;
  layoutRunning: boolean;
}

export function useSigma(containerRef: React.RefObject<HTMLDivElement | null>, graph: Graph | null) {
  const sigmaRef = useRef<Sigma | null>(null);
  const layoutRef = useRef<FA2Layout | null>(null);
  const selectedNodeRef = useRef<string | null>(null);
  const hoveredNodeRef = useRef<string | null>(null);
  const [state, setState] = useState<SigmaState>({
    selectedNode: null,
    hoveredNode: null,
    layoutRunning: false,
  });

  useEffect(() => {
    if (!containerRef.current || !graph) return;

    if (sigmaRef.current) {
      sigmaRef.current.kill();
      sigmaRef.current = null;
    }
    if (layoutRef.current) {
      layoutRef.current.kill();
      layoutRef.current = null;
    }

    const nodeCount = graph.order;
    let gravity = 0.8, scalingRatio = 15, slowDown = 1;
    if (nodeCount > 500) { gravity = 0.5; scalingRatio = 30; slowDown = 2; }
    if (nodeCount > 2000) { gravity = 0.3; scalingRatio = 60; slowDown = 3; }

    const sigma = new Sigma(graph, containerRef.current, {
      allowInvalidContainer: true,
      renderEdgeLabels: false,
      labelRenderedSizeThreshold: 8,
      labelDensity: 0.15,
      labelGridCellSize: 70,
      labelFont: '"JetBrains Mono", monospace',
      labelColor: { color: '#e4e4ed' },
      labelSize: 11,
      stagePadding: 50,
      edgeProgramClasses: {
        curved: EdgeCurveProgram,
      },
      nodeReducer: (node, data) => {
        const res = { ...data };
        const selected = selectedNodeRef.current;
        const hovered = hoveredNodeRef.current;

        if (selected) {
          if (node === selected) {
            res.highlighted = true;
            res.size = (data.size || 6) * 1.5;
          } else if (graph.hasEdge(node, selected) || graph.hasEdge(selected, node)) {
            res.size = (data.size || 6) * 1.3;
          } else {
            res.color = dimColor(data.color || '#475569', 0.2);
            res.size = (data.size || 6) * 0.5;
            res.label = '';
          }
        } else if (hovered) {
          if (node !== hovered && !graph.hasEdge(node, hovered) && !graph.hasEdge(hovered, node)) {
            res.color = dimColor(data.color || '#475569', 0.3);
            res.size = (data.size || 6) * 0.7;
            res.label = '';
          }
        }

        return res;
      },
      edgeReducer: (edge, data) => {
        const res = { ...data };
        const selected = selectedNodeRef.current;

        if (selected) {
          const extremities = graph.extremities(edge);
          if (extremities[0] !== selected && extremities[1] !== selected) {
            res.hidden = true;
          }
        }

        return res;
      },
    });

    sigma.on('clickNode', ({ node }) => {
      const newSelected = selectedNodeRef.current === node ? null : node;
      selectedNodeRef.current = newSelected;
      setState(prev => ({ ...prev, selectedNode: newSelected }));
      sigma.refresh();
    });

    sigma.on('clickStage', () => {
      selectedNodeRef.current = null;
      setState(prev => ({ ...prev, selectedNode: null }));
      sigma.refresh();
    });

    sigma.on('enterNode', ({ node }) => {
      hoveredNodeRef.current = node;
      setState(prev => ({ ...prev, hoveredNode: node }));
      if (containerRef.current) containerRef.current.style.cursor = 'pointer';
      sigma.refresh();
    });

    sigma.on('leaveNode', () => {
      hoveredNodeRef.current = null;
      setState(prev => ({ ...prev, hoveredNode: null }));
      if (containerRef.current) containerRef.current.style.cursor = 'grab';
      sigma.refresh();
    });

    sigmaRef.current = sigma;

    // Start ForceAtlas2 layout in Web Worker
    const layout = new FA2Layout(graph, {
      settings: {
        gravity,
        scalingRatio,
        slowDown,
        barnesHutOptimize: nodeCount > 100,
        barnesHutTheta: 0.6,
        strongGravityMode: false,
        adjustSizes: true,
      },
    });

    layout.start();
    layoutRef.current = layout;
    setState(prev => ({ ...prev, layoutRunning: true }));

    const stopTimeout = nodeCount < 500 ? 10000 : nodeCount < 2000 ? 20000 : 30000;
    const timer = setTimeout(() => {
      if (layoutRef.current) {
        layoutRef.current.stop();
        setState(prev => ({ ...prev, layoutRunning: false }));
      }
    }, stopTimeout);

    return () => {
      clearTimeout(timer);
      if (layoutRef.current) {
        layoutRef.current.kill();
        layoutRef.current = null;
      }
      if (sigmaRef.current) {
        sigmaRef.current.kill();
        sigmaRef.current = null;
      }
    };
  }, [graph, containerRef]);

  const zoomIn = useCallback(() => {
    sigmaRef.current?.getCamera().animatedZoom({ duration: 200 });
  }, []);

  const zoomOut = useCallback(() => {
    sigmaRef.current?.getCamera().animatedUnzoom({ duration: 200 });
  }, []);

  const resetCamera = useCallback(() => {
    sigmaRef.current?.getCamera().animatedReset({ duration: 300 });
  }, []);

  const focusNode = useCallback((nodeId: string) => {
    if (!sigmaRef.current || !graph?.hasNode(nodeId)) return;
    const displayData = sigmaRef.current.getNodeDisplayData(nodeId);
    if (!displayData) return;
    sigmaRef.current.getCamera().animate(
      { x: displayData.x, y: displayData.y, ratio: 0.15 },
      { duration: 400 },
    );
  }, [graph]);

  const toggleLayout = useCallback(() => {
    if (!layoutRef.current) return;
    if (state.layoutRunning) {
      layoutRef.current.stop();
      setState(prev => ({ ...prev, layoutRunning: false }));
    } else {
      layoutRef.current.start();
      setState(prev => ({ ...prev, layoutRunning: true }));
    }
  }, [state.layoutRunning]);

  return {
    sigma: sigmaRef,
    state,
    zoomIn,
    zoomOut,
    resetCamera,
    focusNode,
    toggleLayout,
  };
}
