import React from 'react';
import { FileText } from 'lucide-react';

interface Chunk {
    chunk_id: string;
    document_id?: string;
    text: string;
    similarity_score: number;
}

interface ResultsProps {
    response: string | null;
    chunks: Chunk[];
}

export const Results: React.FC<ResultsProps> = ({ response, chunks }) => {
    if (!response && chunks.length === 0) return null;

    return (
        <div className="w-full">
            {response && (
                <section className="enter">
                    <div className="mb-2 flex items-baseline justify-between">
                        <h2 className="text-[13px] font-medium text-ink">Answer</h2>
                        <span className="font-mono text-[11px] text-ink-muted">
                            local model
                        </span>
                    </div>
                    <div className="rounded-[12px] border border-paper-line bg-paper-card p-5 text-[15px] leading-7 text-ink">
                        {response}
                    </div>
                </section>
            )}

            {chunks.length > 0 && (
                <section className="mt-6">
                    <div className="mb-2 flex items-baseline justify-between">
                        <h2 className="text-[13px] font-medium text-ink">Sources</h2>
                        <span className="font-mono text-[11px] tnum text-ink-muted">
                            {chunks.length} chunks
                        </span>
                    </div>
                    <div className="grid gap-3 md:grid-cols-2">
                        {chunks.map((chunk, i) => {
                            const score = Math.max(0, Math.min(1, chunk.similarity_score));
                            return (
                                <article
                                    key={chunk.chunk_id || i}
                                    className="rounded-[10px] border border-paper-line bg-paper-card p-4 transition-colors duration-150 hover:border-ink-muted"
                                >
                                    <div className="flex items-center justify-between gap-3">
                                        <div className="flex min-w-0 items-center gap-2">
                                            <FileText size={16} strokeWidth={1.5} className="shrink-0 text-ink-muted" />
                                            <span className="truncate text-[13px] font-medium text-ink">
                                                {chunk.document_id || chunk.chunk_id}
                                            </span>
                                        </div>
                                        <span className="shrink-0 font-mono text-[11px] tnum text-ink-secondary">
                                            {score.toFixed(2)}
                                        </span>
                                    </div>
                                    <div className="mt-2 h-[2px] w-full bg-paper-line">
                                        <div
                                            className="h-[2px] bg-wax"
                                            style={{ width: `${score * 100}%` }}
                                        />
                                    </div>
                                    <p className="mt-3 line-clamp-4 text-[13px] leading-6 text-ink-secondary">
                                        {chunk.text}
                                    </p>
                                </article>
                            );
                        })}
                    </div>
                </section>
            )}
        </div>
    );
};
