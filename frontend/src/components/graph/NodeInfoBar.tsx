interface NodeInfoBarProps {
  nodeData: Record<string, any>;
  onFocus: () => void;
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-[11px] text-ink-muted">{label}</dt>
      <dd className="truncate font-mono text-[11px] tnum text-ink">{value}</dd>
    </div>
  );
}

export function NodeInfoBar({ nodeData, onFocus }: NodeInfoBarProps) {
  const isQuery = nodeData.nodeType === 'query';
  const similarity = typeof nodeData.maxSimilarity === 'number' ? nodeData.maxSimilarity : null;

  return (
    <div>
      <div className="flex items-center justify-between pb-2">
        <h2 className="text-[13px] font-medium text-ink">Selection</h2>
        <button
          onClick={onFocus}
          className="text-[11px] text-wax transition-colors duration-150 hover:text-wax-dim"
        >
          Focus
        </button>
      </div>

      <dl className="space-y-1.5">
        <Row label="Type" value={isQuery ? 'query' : 'chunk'} />
        <Row label="Document" value={isQuery ? '—' : nodeData.documentName} />
        {!isQuery && <Row label="Chunk" value={`#${nodeData.chunkNumber}`} />}
        <Row label="Tokens" value={nodeData.tokenCount > 0 ? String(nodeData.tokenCount) : '—'} />
        <Row label="Max similarity" value={similarity !== null ? similarity.toFixed(2) : '—'} />
      </dl>

      {nodeData.textPreview && (
        <p className="mt-3 border-t border-paper-line pt-3 text-[12px] leading-5 text-ink-secondary">
          {nodeData.textPreview}
        </p>
      )}
    </div>
  );
}
