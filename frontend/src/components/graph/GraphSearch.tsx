import { useState } from 'react';
import { Search } from 'lucide-react';

interface GraphSearchProps {
  onSearch: (query: string) => void;
  loading: boolean;
}

export function GraphSearch({ onSearch, loading }: GraphSearchProps) {
  const [query, setQuery] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query.trim());
    }
  };

  return (
    <form onSubmit={handleSubmit} className="relative w-56 shrink-0">
      <label htmlFor="graph-search" className="sr-only">Search chunks by meaning</label>
      <input
        id="graph-search"
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search chunks"
        className="h-8 w-full rounded-[8px] border border-paper-line bg-paper-card pl-8 pr-8 text-[12px] text-ink placeholder:text-ink-muted focus:outline-none"
      />
      <Search
        size={16}
        strokeWidth={1.5}
        className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-muted"
      />
      {loading && (
        <div className="absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 animate-spin rounded-full border-2 border-ink-muted border-t-transparent" />
      )}
    </form>
  );
}
