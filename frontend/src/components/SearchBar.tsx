import React, { useState } from 'react';
import { Search } from 'lucide-react';

interface SearchBarProps {
    onSearch: (query: string) => void;
    isLoading?: boolean;
}

export const SearchBar: React.FC<SearchBarProps> = ({ onSearch, isLoading }) => {
    const [query, setQuery] = useState('');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (query.trim()) {
            onSearch(query);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="mt-5 w-full">
            <div className="flex items-center gap-2 rounded-[10px] border border-paper-line bg-paper-card px-3 transition-colors duration-150 focus-within:border-ink-muted">
                <Search size={16} strokeWidth={1.5} className="shrink-0 text-ink-muted" />
                <label htmlFor="query" className="sr-only">Question</label>
                <input
                    id="query"
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search documents"
                    className="h-11 w-full bg-transparent text-[15px] text-ink placeholder:text-ink-muted focus:outline-none"
                    disabled={isLoading}
                />
                {isLoading && (
                    <div className="mr-1 h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-ink-muted border-t-transparent" />
                )}
                <button
                    type="submit"
                    disabled={isLoading || !query.trim()}
                    className="h-9 shrink-0 rounded-[8px] bg-wax px-4 text-[13px] font-medium text-white transition-colors duration-150 hover:bg-wax-dim disabled:opacity-40"
                >
                    Ask
                </button>
            </div>
        </form>
    );
};
