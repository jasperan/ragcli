import Graph from 'graphology';
import type { GraphData, GraphNode } from '../hooks/useGraphData';

const BG = { r: 0xf7, g: 0xf4, b: 0xee };

export function dimColor(hex: string, amount: number): string {
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
  const nr = Math.round(r * amount + BG.r * (1 - amount));
  const ng = Math.round(g * amount + BG.g * (1 - amount));
  const nb = Math.round(b * amount + BG.b * (1 - amount));
  return `rgb(${nr},${ng},${nb})`;
}

const COLORS = {
  query: '#B3341F',
  highSim: '#1F1B16',
  midSim: '#6B625A',
  lowSim: '#CFC7B9',
  edge: {
    high: '#57504A',
    mid: '#8A8177',
    low: '#DED7CA',
  },
};

function getNodeSize(node: GraphNode): number {
  if (node.node_type === 'query') return 12;
  return 6;
}

function getEdgeColor(similarity: number): string {
  if (similarity >= 0.8) return COLORS.edge.high;
  if (similarity >= 0.6) return COLORS.edge.mid;
  return COLORS.edge.low;
}

function getEdgeSize(similarity: number): number {
  return 1 + (similarity * 3);
}

export function buildGraph(data: GraphData): Graph {
  const graph = new Graph({ type: 'undirected', multi: false });

  // Track max similarity per node for coloring
  const nodeMaxSimilarity = new Map<string, number>();
  for (const edge of data.edges) {
    const currentSource = nodeMaxSimilarity.get(edge.source) || 0;
    const currentTarget = nodeMaxSimilarity.get(edge.target) || 0;
    nodeMaxSimilarity.set(edge.source, Math.max(currentSource, edge.similarity));
    nodeMaxSimilarity.set(edge.target, Math.max(currentTarget, edge.similarity));
  }

  // Golden angle distribution for initial positions
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  const totalNodes = data.nodes.length;

  data.nodes.forEach((node, index) => {
    const angle = index * goldenAngle;
    const radius = 100 * Math.sqrt((index + 1) / totalNodes);
    const x = Math.cos(angle) * radius;
    const y = Math.sin(angle) * radius;

    const maxSim = nodeMaxSimilarity.get(node.id) || 0;
    let color: string;
    if (node.node_type === 'query') {
      color = COLORS.query;
    } else if (maxSim >= 0.8) {
      color = COLORS.highSim;
    } else if (maxSim >= 0.5) {
      color = COLORS.midSim;
    } else {
      color = COLORS.lowSim;
    }

    graph.addNode(node.id, {
      x,
      y,
      size: getNodeSize(node),
      color,
      label: node.node_type === 'query'
        ? `Query: ${node.text_preview.substring(0, 30)}...`
        : `${node.document_name} #${node.chunk_number}`,
      nodeType: node.node_type,
      documentId: node.document_id,
      documentName: node.document_name,
      chunkNumber: node.chunk_number,
      textPreview: node.text_preview,
      tokenCount: node.token_count,
      maxSimilarity: maxSim,
    });
  });

  data.edges.forEach((edge) => {
    if (graph.hasNode(edge.source) && graph.hasNode(edge.target)) {
      graph.addEdge(edge.source, edge.target, {
        size: getEdgeSize(edge.similarity),
        color: getEdgeColor(edge.similarity),
        similarity: edge.similarity,
        type: 'curved',
      });
    }
  });

  return graph;
}
