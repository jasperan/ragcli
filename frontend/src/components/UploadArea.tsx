import React, { useRef, useState } from 'react';
import { Upload, FileText } from 'lucide-react';
import { clsx } from 'clsx';

interface UploadAreaProps {
    onUpload: (file: File) => Promise<void>;
    isUploading?: boolean;
}

export const UploadArea: React.FC<UploadAreaProps> = ({ onUpload, isUploading }) => {
    const inputRef = useRef<HTMLInputElement>(null);
    const [dragActive, setDragActive] = useState(false);
    const [fileName, setFileName] = useState<string | null>(null);

    const handleDrag = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === "dragenter" || e.type === "dragover") {
            setDragActive(true);
        } else if (e.type === "dragleave") {
            setDragActive(false);
        }
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            handleFile(e.dataTransfer.files[0]);
        }
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        e.preventDefault();
        if (e.target.files && e.target.files[0]) {
            handleFile(e.target.files[0]);
        }
    };

    const handleFile = async (file: File) => {
        setFileName(file.name);
        await onUpload(file);
        setTimeout(() => setFileName(null), 4000); // Clear after 4s
    };

    return (
        <div
            className={clsx(
                "rounded-[12px] border bg-paper-card p-4 transition-colors duration-150",
                dragActive ? "border-wax" : "border-paper-line",
                isUploading && "opacity-60"
            )}
        >
            <div className="flex items-center justify-between">
                <h2 className="text-[13px] font-medium text-ink">Add a document</h2>
                <span className="font-mono text-[11px] text-ink-muted">index</span>
            </div>

            <div
                className={clsx(
                    "mt-3 flex cursor-pointer flex-col items-start gap-2 rounded-[8px] border border-dashed px-4 py-5 transition-colors duration-150",
                    dragActive ? "border-wax bg-wax-soft" : "border-paper-line hover:border-ink-muted"
                )}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                onClick={() => inputRef.current?.click()}
            >
                <input
                    ref={inputRef}
                    type="file"
                    className="hidden"
                    onChange={handleChange}
                    disabled={isUploading}
                />

                <div className="flex items-center gap-2">
                    <Upload size={16} strokeWidth={1.5} className="text-ink-muted" />
                    <span className="text-[13px] font-medium text-ink">
                        Drop a file, or choose one
                    </span>
                </div>

                {fileName ? (
                    <div className="flex min-w-0 items-center gap-2 text-ink-secondary">
                        <FileText size={16} strokeWidth={1.5} className="shrink-0 text-ink-muted" />
                        <span className="truncate font-mono text-[11px]">{fileName}</span>
                        <span className="shrink-0 text-[11px] text-ink-muted">indexed</span>
                    </div>
                ) : (
                    <p className="text-[11px] text-ink-muted">PDF, TXT, MD</p>
                )}
            </div>
        </div>
    );
};
