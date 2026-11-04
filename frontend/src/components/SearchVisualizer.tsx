import React, { useCallback, useEffect, useRef, useState } from 'react';

interface ChunkResult {
    chunk_id: string;
    document_id: string;
    text: string;
    similarity_score: number;
    embedding?: number[];
}

interface SearchVisualizerProps {
    queryEmbedding?: number[];
    chunks: ChunkResult[];
}

interface BandRow {
    kind: 'query' | 'embedding' | 'contribution';
    label: string;
    note?: string;
    y: number;
    h: number;
    values: number[];
    strongest?: number;
}

interface Geometry {
    gutter: number;
    right: number;
    barWidth: number;
    plotTop: number;
    rows: BandRow[];
    axisY: number;
}

const PAPER_RGB = [253, 251, 247];
const INK_RGB = [31, 27, 22];
const WAX_RGB = [179, 52, 31];
const WAX = '#B3341F';

const COLORS = {
    empty: '#F1EDE5',
    label: '#57504A',
    muted: '#7A7268',
    axis: '#D8D1C4',
};

const GUTTER = 112;
const PAD_RIGHT = 20;
const ROW_H = 16;
const CONTR_H = 8;
const ROW_GAP = 6;
const BLOCK_GAP = 16;
const TOP = 8;
const AXIS_H = 26;
const FONT = '11px "IBM Plex Mono", ui-monospace, monospace';
const TICK_FONT = '10px "IBM Plex Mono", ui-monospace, monospace';

function mix(a: number[], b: number[], t: number): string {
    return `rgb(${Math.round(a[0] + (b[0] - a[0]) * t)},${Math.round(
        a[1] + (b[1] - a[1]) * t,
    )},${Math.round(a[2] + (b[2] - a[2]) * t)})`;
}

function bandColor(value: number, maxAbs: number): string {
    if (!maxAbs || Math.abs(value) < 1e-9) return COLORS.empty;
    const t = Math.min(0.94, Math.pow(Math.abs(value) / maxAbs, 0.6));
    return mix(PAPER_RGB, value > 0 ? WAX_RGB : INK_RGB, t);
}

export const SearchVisualizer: React.FC<SearchVisualizerProps> = ({ queryEmbedding, chunks }) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const wrapRef = useRef<HTMLDivElement>(null);
    const geometryRef = useRef<Geometry | null>(null);
    const [width, setWidth] = useState(0);
    const [tooltip, setTooltip] = useState<{
        x: number;
        y: number;
        label: string;
        dim: number;
        value: number;
    } | null>(null);

    const drawable = Boolean(queryEmbedding && queryEmbedding.length > 0 && chunks.some(c => c.embedding));

    useEffect(() => {
        const wrap = wrapRef.current;
        if (!wrap) return;
        const observer = new ResizeObserver(() => setWidth(wrap.clientWidth));
        observer.observe(wrap);
        setWidth(wrap.clientWidth);
        return () => observer.disconnect();
    }, []);

    const draw = useCallback(() => {
        const canvas = canvasRef.current;
        const dim = queryEmbedding?.length ?? 0;
        if (!canvas || !width || !dim || !drawable) return;

        const withEmbedding = chunks.filter(c => c.embedding && c.embedding.length >= dim);
        const lineCount = withEmbedding.length;

        const height =
            TOP + ROW_H + BLOCK_GAP + lineCount * (ROW_H + ROW_GAP + CONTR_H + BLOCK_GAP) + AXIS_H;

        const dpr = window.devicePixelRatio || 1;
        canvas.width = Math.round(width * dpr);
        canvas.height = Math.round(height * dpr);
        canvas.style.height = `${height}px`;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.fillStyle = '#FDFBF7';
        ctx.fillRect(0, 0, width, height);

        const plotLeft = GUTTER;
        const plotRight = width - PAD_RIGHT;
        const barWidth = (plotRight - plotLeft) / dim;

        // One shared scale for every embedding row.
        let maxAbsEmb = 0;
        const allVectors = [queryEmbedding!, ...withEmbedding.map(c => c.embedding!)];
        for (const vector of allVectors) {
            for (let i = 0; i < dim; i++) {
                const v = Math.abs(vector[i]);
                if (v > maxAbsEmb) maxAbsEmb = v;
            }
        }

        const rows: BandRow[] = [];

        const drawBands = (y: number, h: number, values: number[], maxAbs: number) => {
            for (let i = 0; i < dim; i++) {
                ctx.fillStyle = bandColor(values[i], maxAbs);
                ctx.fillRect(plotLeft + i * barWidth, y, Math.ceil(barWidth), h);
            }
        };

        const drawLabel = (text: string, y: number, h: number, color: string, weight = '400') => {
            ctx.font = `${weight} ${FONT}`;
            ctx.fillStyle = color;
            ctx.textAlign = 'right';
            ctx.textBaseline = 'middle';
            ctx.fillText(text, plotLeft - 10, y + h / 2);
            ctx.textAlign = 'left';
        };

        // Query row
        let y = TOP;
        drawBands(y, ROW_H, queryEmbedding!, maxAbsEmb || 1);
        drawLabel('query', y, ROW_H, COLORS.label, '500');
        rows.push({ kind: 'query', label: 'query', y, h: ROW_H, values: queryEmbedding! });
        y += ROW_H + BLOCK_GAP;

        // One block per retrieved chunk: embedding row + contribution strip
        withEmbedding.forEach((chunk, idx) => {
            const embeddingTop = y;
            drawBands(y, ROW_H, chunk.embedding!, maxAbsEmb || 1);
            drawLabel(`#${idx + 1} ${chunk.similarity_score.toFixed(2)}`, y, ROW_H, COLORS.label);
            rows.push({
                kind: 'embedding',
                label: `#${idx + 1} embedding`,
                y,
                h: ROW_H,
                values: chunk.embedding!,
            });
            y += ROW_H + ROW_GAP;

            const contribution = new Array<number>(dim);
            let maxAbsContrib = 0;
            let strongest = 0;
            for (let i = 0; i < dim; i++) {
                const c = queryEmbedding![i] * chunk.embedding![i];
                contribution[i] = c;
                const abs = Math.abs(c);
                if (abs > maxAbsContrib) {
                    maxAbsContrib = abs;
                    strongest = i;
                }
            }

            drawBands(y, CONTR_H, contribution, maxAbsContrib || 1);
            drawLabel(`d${strongest}`, y, CONTR_H, WAX, '500');

            // Signature mark: a 2px wax rule under the band that carried the hit.
            ctx.fillStyle = WAX;
            ctx.fillRect(
                plotLeft + strongest * barWidth,
                y + CONTR_H + 2,
                Math.max(2, barWidth),
                2,
            );
            // Measurement tick through both rows, on the same dimension.
            ctx.fillRect(
                plotLeft + strongest * barWidth,
                embeddingTop,
                1.2,
                y + CONTR_H + 3 - embeddingTop,
            );

            rows.push({
                kind: 'contribution',
                label: `#${idx + 1} contribution`,
                note: `d${strongest}`,
                y,
                h: CONTR_H,
                values: contribution,
                strongest,
            });

            y += CONTR_H + BLOCK_GAP;
        });

        // Dimension axis
        ctx.strokeStyle = COLORS.axis;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(plotLeft, y - 10);
        ctx.lineTo(plotRight, y - 10);
        ctx.stroke();

        ctx.font = TICK_FONT;
        ctx.fillStyle = COLORS.muted;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        const step = dim > 1024 ? 128 : 64;
        for (let i = 0; i <= dim; i += 64) {
            const x = plotLeft + i * barWidth;
            const tall = i % step === 0;
            ctx.beginPath();
            ctx.moveTo(x, y - 10);
            ctx.lineTo(x, y - (tall ? 4 : 7));
            ctx.stroke();
            if (tall && i < dim) {
                ctx.fillText(String(i), x, y - 2);
            }
        }
        ctx.textAlign = 'left';

        geometryRef.current = {
            gutter: plotLeft,
            right: plotRight,
            barWidth,
            plotTop: TOP,
            rows,
            axisY: y,
        };
    }, [queryEmbedding, chunks, width, drawable]);

    useEffect(() => {
        draw();
    }, [draw]);

    const handleMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
        const canvas = canvasRef.current;
        const geometry = geometryRef.current;
        if (!canvas || !geometry) return;
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        if (x < geometry.gutter || x > geometry.right) {
            setTooltip(null);
            return;
        }
        const dim = Math.floor((x - geometry.gutter) / geometry.barWidth);
        const row = geometry.rows.find(r => y >= r.y && y <= r.y + r.h);
        if (!row || dim < 0 || dim >= row.values.length) {
            setTooltip(null);
            return;
        }
        setTooltip({
            x: Math.min(x + 12, geometry.right - 8),
            y: Math.max(row.y - 8, 0),
            label: row.label,
            dim,
            value: row.values[dim],
        });
    };

    if (!queryEmbedding || chunks.length === 0 || !drawable) return null;

    const dim = queryEmbedding.length;
    const scored = chunks.filter(c => c.embedding);
    const best = scored.reduce(
        (acc, c) => (c.similarity_score > acc.similarity_score ? c : acc),
        scored[0],
    );

    let bestDim = 0;
    if (best?.embedding) {
        let maxAbs = 0;
        for (let i = 0; i < dim; i++) {
            const abs = Math.abs((queryEmbedding[i] ?? 0) * (best.embedding[i] ?? 0));
            if (abs > maxAbs) {
                maxAbs = abs;
                bestDim = i;
            }
        }
    }

    return (
        <section className="enter rounded-[12px] border border-paper-line bg-paper-card">
            <header className="flex items-baseline justify-between px-5 pt-4">
                <h2 className="text-[13px] font-medium text-ink">Embedding contribution</h2>
                <span className="font-mono text-[11px] tnum text-ink-muted">
                    {dim} dims · {scored.length} chunks
                </span>
            </header>
            <p className="px-5 pt-1 text-[12px] text-ink-secondary">
                Query vector against each retrieved chunk, element by element. The wax tick marks the
                dimension that carried that chunk's similarity; for the top chunk it is{' '}
                <span className="font-mono tnum">d{bestDim}</span>.
            </p>

            <div ref={wrapRef} className="relative mt-3 px-5">
                <canvas
                    ref={canvasRef}
                    onMouseMove={handleMove}
                    onMouseLeave={() => setTooltip(null)}
                    className="block w-full"
                />
                {tooltip && (
                    <div
                        className="pointer-events-none absolute z-10 rounded-[6px] border border-paper-line bg-paper-card px-2 py-1 font-mono text-[11px] tnum text-ink"
                        style={{ left: tooltip.x, top: tooltip.y }}
                    >
                        <span className="text-ink-muted">{tooltip.label}</span> · d{tooltip.dim} ·{' '}
                        {tooltip.value.toFixed(3)}
                    </div>
                )}
            </div>

            <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-paper-line px-5 py-3">
                <div className="flex items-center gap-2">
                    <span className="font-mono text-[11px] text-ink-muted">−</span>
                    <span className="h-2 w-24 rounded-[2px] border border-paper-line bg-[linear-gradient(90deg,#8E8378_0%,#F1EDE5_50%,#B3341F_100%)]" />
                    <span className="font-mono text-[11px] text-ink-muted">+</span>
                    <span className="ml-1 font-mono text-[11px] text-ink-muted">
                        q[i] × d[i], each row scaled to its own max
                    </span>
                </div>
                <span className="font-mono text-[11px] tnum text-ink-secondary">
                    top score {Math.max(...chunks.map(c => c.similarity_score)).toFixed(2)}
                </span>
            </footer>
        </section>
    );
};
