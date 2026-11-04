import { useState } from 'react';
import axios from 'axios';
import { SearchBar } from '../components/SearchBar';
import { UploadArea } from '../components/UploadArea';
import { Results } from '../components/Results';
import { SearchVisualizer } from '../components/SearchVisualizer';

export function Home() {
  const [response, setResponse] = useState<string | null>(null);
  const [chunks, setChunks] = useState<any[]>([]);
  const [queryEmbedding, setQueryEmbedding] = useState<number[] | undefined>(undefined);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (query: string) => {
    setIsLoading(true);
    setResponse(null);
    setChunks([]);
    setQueryEmbedding(undefined);
    setError(null);
    try {
      const res = await axios.post('/api/query', {
        query,
        top_k: 5,
        min_similarity: 0.0,
        include_embeddings: true
      });
      setResponse(res.data.response);
      setChunks(res.data.chunks || []);
      setQueryEmbedding(res.data.query_embedding);
    } catch (err) {
      console.error("Search failed", err);
      setError("The query did not run. Check that the ragcli API is reachable, then ask again.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpload = async (file: File) => {
    setIsUploading(true);
    setError(null);
    const formData = new FormData();
    formData.append('file', file);
    try {
      await axios.post('/api/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
    } catch (err) {
      console.error("Upload failed", err);
      setError("The file was not indexed. Check that the ragcli API is reachable, then try again.");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <main className="mx-auto grid w-full max-w-shell gap-6 px-6 py-8 lg:grid-cols-[minmax(0,1fr)_320px]">
      <section className="min-w-0">
        <h1 className="text-[24px] font-medium leading-8 tracking-tight text-ink">
          Ask your documents
        </h1>
        <p className="mt-1 text-[13px] text-ink-secondary">
          Answers cite the chunks and embedding dimensions that produced them.
        </p>

        <SearchBar onSearch={handleSearch} isLoading={isLoading} />

        {!response && !isLoading && !error && (
          <div className="mt-6 rounded-[12px] border border-paper-line bg-paper-card p-5">
            <div className="flex items-baseline justify-between">
              <p className="text-[13px] font-medium text-ink">Nothing asked yet</p>
              <span className="font-mono text-[11px] text-ink-muted">no query</span>
            </div>
            <dl className="mt-4 grid gap-4 sm:grid-cols-3">
              <div>
                <dt className="text-[12px] font-medium text-ink">Answer</dt>
                <dd className="mt-1 text-[12px] leading-5 text-ink-secondary">
                  One answer written from the retrieved text, not a list of links.
                </dd>
              </div>
              <div>
                <dt className="text-[12px] font-medium text-ink">Sources</dt>
                <dd className="mt-1 text-[12px] leading-5 text-ink-secondary">
                  Every chunk that fed the answer, with its similarity to the question.
                </dd>
              </div>
              <div>
                <dt className="text-[12px] font-medium text-ink">Contribution</dt>
                <dd className="mt-1 text-[12px] leading-5 text-ink-secondary">
                  The embedding dimensions behind the match, drawn element by element.
                </dd>
              </div>
            </dl>
          </div>
        )}

        {error && (
          <div className="mt-4 rounded-[10px] border border-wax/30 bg-wax-soft px-4 py-3">
            <p className="text-[13px] leading-5 text-wax-dim">{error}</p>
          </div>
        )}

        <div className="mt-6 space-y-6">
          {response && (
            <SearchVisualizer queryEmbedding={queryEmbedding} chunks={chunks} />
          )}
          <Results response={response} chunks={chunks} />
        </div>
      </section>

      <aside className="h-fit space-y-3 lg:sticky lg:top-20">
        <UploadArea onUpload={handleUpload} isUploading={isUploading} />
        <p className="px-1 font-mono text-[11px] leading-5 text-ink-muted">
          Files stay on this machine. Ask a question to read the index, or add a document to grow it.
        </p>
      </aside>
    </main>
  );
}
