import { useState, useEffect } from 'react';
import { SlidersHorizontal, ChevronDown, ChevronUp } from 'lucide-react';
import type { GraphFilters } from '../../hooks/useGraphData';

interface FilterPanelProps {
  filters: GraphFilters;
  onApply: (filters: Partial<GraphFilters>) => void;
  loading: boolean;
}

export function FilterPanel({ filters, onApply, loading }: FilterPanelProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [localFilters, setLocalFilters] = useState(filters);

  useEffect(() => {
    setLocalFilters(filters);
  }, [filters]);

  const handleApply = () => {
    onApply(localFilters);
  };

  return (
    <div>
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex w-full items-center gap-2 pb-2 text-left"
      >
        <SlidersHorizontal size={16} strokeWidth={1.5} className="text-ink-muted" />
        <h2 className="text-[13px] font-medium text-ink">Filters</h2>
        <span className="ml-auto text-ink-muted">
          {collapsed ? <ChevronDown size={16} strokeWidth={1.5} /> : <ChevronUp size={16} strokeWidth={1.5} />}
        </span>
      </button>

      {!collapsed && (
        <div className="space-y-4">
          <div>
            <div className="mb-1 flex items-baseline justify-between">
              <label htmlFor="min-similarity" className="text-[11px] text-ink-secondary">
                Min similarity
              </label>
              <span className="font-mono text-[11px] tnum text-ink">{localFilters.minSimilarity.toFixed(2)}</span>
            </div>
            <input
              id="min-similarity"
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={localFilters.minSimilarity}
              onChange={(e) => setLocalFilters(f => ({ ...f, minSimilarity: parseFloat(e.target.value) }))}
              className="w-full accent-wax"
            />
          </div>

          <div>
            <div className="mb-1 flex items-baseline justify-between">
              <label htmlFor="top-k" className="text-[11px] text-ink-secondary">
                Neighbors per chunk
              </label>
              <span className="font-mono text-[11px] tnum text-ink">{localFilters.topK}</span>
            </div>
            <input
              id="top-k"
              type="range"
              min="1"
              max="50"
              step="1"
              value={localFilters.topK}
              onChange={(e) => setLocalFilters(f => ({ ...f, topK: parseInt(e.target.value) }))}
              className="w-full accent-wax"
            />
          </div>

          <div>
            <div className="mb-1 flex items-baseline justify-between">
              <label htmlFor="max-nodes" className="text-[11px] text-ink-secondary">
                Max nodes
              </label>
              <span className="font-mono text-[11px] tnum text-ink">{localFilters.limit}</span>
            </div>
            <input
              id="max-nodes"
              type="range"
              min="10"
              max="2000"
              step="10"
              value={localFilters.limit}
              onChange={(e) => setLocalFilters(f => ({ ...f, limit: parseInt(e.target.value) }))}
              className="w-full accent-wax"
            />
          </div>

          <button
            onClick={handleApply}
            disabled={loading}
            className="h-9 w-full rounded-[8px] bg-wax text-[13px] font-medium text-white transition-colors duration-150 hover:bg-wax-dim disabled:opacity-40"
          >
            {loading ? 'Loading' : 'Apply filters'}
          </button>
        </div>
      )}
    </div>
  );
}
