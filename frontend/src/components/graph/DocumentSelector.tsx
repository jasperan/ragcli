import { useState, useMemo } from 'react';
import { FileText, ChevronDown, ChevronRight, Hash, Eye, EyeOff } from 'lucide-react';
import type { GraphData } from '../../hooks/useGraphData';

interface DocumentInfo {
  documentId: string;
  documentName: string;
  chunkCount: number;
  nodeIds: string[];
}

interface DocumentSelectorProps {
  data: GraphData | null;
  selectedDocumentId: string | null;
  onSelectDocument: (docId: string | null) => void;
  onFocusNode: (nodeId: string) => void;
}

export function DocumentSelector({ data, selectedDocumentId, onSelectDocument, onFocusNode }: DocumentSelectorProps) {
  const [expandedDoc, setExpandedDoc] = useState<string | null>(null);

  const documents = useMemo(() => {
    if (!data) return [];
    const docMap = new Map<string, DocumentInfo>();
    for (const node of data.nodes) {
      if (node.node_type === 'query') continue;
      const existing = docMap.get(node.document_id);
      if (existing) {
        existing.chunkCount++;
        existing.nodeIds.push(node.id);
      } else {
        docMap.set(node.document_id, {
          documentId: node.document_id,
          documentName: node.document_name,
          chunkCount: 1,
          nodeIds: [node.id],
        });
      }
    }
    return Array.from(docMap.values()).sort((a, b) => b.chunkCount - a.chunkCount);
  }, [data]);

  const chunks = useMemo(() => {
    if (!data || !expandedDoc) return [];
    return data.nodes
      .filter(n => n.document_id === expandedDoc && n.node_type !== 'query')
      .sort((a, b) => a.chunk_number - b.chunk_number);
  }, [data, expandedDoc]);

  const handleDocClick = (docId: string) => {
    if (selectedDocumentId === docId) {
      onSelectDocument(null);
    } else {
      onSelectDocument(docId);
    }
  };

  const handleExpandToggle = (e: React.MouseEvent, docId: string) => {
    e.stopPropagation();
    setExpandedDoc(expandedDoc === docId ? null : docId);
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-2 pb-2">
        <FileText size={16} strokeWidth={1.5} className="text-ink-muted" />
        <h2 className="text-[13px] font-medium text-ink">Documents</h2>
        <span className="ml-auto font-mono text-[11px] tnum text-ink-muted">{documents.length}</span>
      </div>

      {documents.length === 0 ? (
        <p className="text-[12px] leading-5 text-ink-secondary">No documents in this graph yet.</p>
      ) : (
        <div className="-mx-1 min-h-0 flex-1 overflow-y-auto">
          {documents.map((doc) => {
            const isSelected = selectedDocumentId === doc.documentId;
            const isExpanded = expandedDoc === doc.documentId;

            return (
              <div key={doc.documentId}>
                <div
                  className={`flex items-center gap-2 rounded-[6px] px-1 py-1.5 transition-colors duration-150 ${
                    isSelected ? 'bg-wax-soft' : 'hover:bg-paper-sunken'
                  }`}
                >
                  <button
                    onClick={(e) => handleExpandToggle(e, doc.documentId)}
                    className="shrink-0 text-ink-muted transition-colors duration-150 hover:text-ink"
                    aria-label={isExpanded ? 'Collapse' : 'Expand'}
                  >
                    {isExpanded ? <ChevronDown size={16} strokeWidth={1.5} /> : <ChevronRight size={16} strokeWidth={1.5} />}
                  </button>

                  <button
                    onClick={() => handleDocClick(doc.documentId)}
                    className="min-w-0 flex-1 text-left"
                  >
                    <p className={`truncate text-[12px] ${isSelected ? 'text-ink' : 'text-ink-secondary'}`}>
                      {doc.documentName}
                    </p>
                    <p className="mt-0.5 font-mono text-[11px] tnum text-ink-muted">
                      {doc.chunkCount} chunk{doc.chunkCount !== 1 ? 's' : ''}
                    </p>
                  </button>

                  <span
                    className={`shrink-0 transition-opacity duration-150 ${
                      isSelected ? 'opacity-100' : 'opacity-0'
                    }`}
                  >
                    {isSelected
                      ? <Eye size={16} strokeWidth={1.5} className="text-wax" />
                      : <EyeOff size={16} strokeWidth={1.5} className="text-ink-muted" />
                    }
                  </span>
                </div>

                {/* Expanded chunk list */}
                {isExpanded && (
                  <div className="ml-4 border-l border-paper-line pl-2">
                    {chunks.map((chunk) => (
                      <button
                        key={chunk.id}
                        onClick={() => onFocusNode(chunk.id)}
                        className="flex w-full items-center gap-2 rounded-[6px] px-1 py-1 text-left transition-colors duration-150 hover:bg-paper-sunken"
                      >
                        <Hash size={16} strokeWidth={1.5} className="shrink-0 text-ink-muted" />
                        <span className="shrink-0 font-mono text-[11px] tnum text-ink-muted">
                          {chunk.chunk_number}
                        </span>
                        <span className="truncate text-[11px] text-ink-secondary">
                          {chunk.text_preview.slice(0, 44)}…
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
