import { ZoomIn, ZoomOut, Maximize2, Play, Pause } from 'lucide-react';

interface GraphControlsProps {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
  onToggleLayout: () => void;
  layoutRunning: boolean;
}

export function GraphControls({ onZoomIn, onZoomOut, onReset, onToggleLayout, layoutRunning }: GraphControlsProps) {
  const btnClass = "flex h-8 w-8 items-center justify-center rounded-[8px] border border-paper-line bg-paper-card text-ink-secondary transition-colors duration-150 hover:border-ink-muted hover:text-ink";

  return (
    <div className="absolute bottom-5 right-5 z-10 flex flex-col gap-1.5">
      <button onClick={onZoomIn} className={btnClass} title="Zoom in">
        <ZoomIn size={16} strokeWidth={1.5} />
      </button>
      <button onClick={onZoomOut} className={btnClass} title="Zoom out">
        <ZoomOut size={16} strokeWidth={1.5} />
      </button>
      <button onClick={onReset} className={btnClass} title="Fit to screen">
        <Maximize2 size={16} strokeWidth={1.5} />
      </button>
      <button onClick={onToggleLayout} className={btnClass} title={layoutRunning ? 'Pause layout' : 'Resume layout'}>
        {layoutRunning ? <Pause size={16} strokeWidth={1.5} /> : <Play size={16} strokeWidth={1.5} />}
      </button>
    </div>
  );
}
