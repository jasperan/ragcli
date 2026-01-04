import { useState } from 'react';
import axios from 'axios';
import { SearchBar } from './components/SearchBar';
import { UploadArea } from './components/UploadArea';
import { Results } from './components/Results';

// Configure Axios base URL
// Ensure backend allows CORS. For dev, we might need proxy in vite.config.ts if CORS is strict.
axios.defaults.baseURL = 'http://localhost:8000';

function App() {
  const [response, setResponse] = useState<string | null>(null);
  const [chunks, setChunks] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  const handleSearch = async (query: string) => {
    setIsLoading(true);
    setResponse(null);
    setChunks([]);
    try {
      // Assuming document_ids=[] implies searching all documents in backend logic or it's optional
      const res = await axios.post('/api/query', {
        query,
        top_k: 5,
        min_similarity: 0.0
      });
      setResponse(res.data.response);
      setChunks(res.data.chunks || []);
    } catch (error) {
      console.error("Search failed", error);
      setResponse("Sorry, I encountered an error while searching.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpload = async (file: File) => {
    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    try {
      await axios.post('/api/documents/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
    } catch (error) {
      console.error("Upload failed", error);
      alert("Upload failed. Please check the backend connection.");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="min-h-screen bg-white">
      <header className="p-6 flex items-center justify-between border-b border-gray-100">
        <div className="flex items-center space-x-2">
          <div className="h-8 w-8 bg-primary-600 rounded-lg flex items-center justify-center text-white font-bold text-lg shadow-sm">
            R
          </div>
          <span className="text-xl font-medium text-gray-700 tracking-tight">ragcli</span>
        </div>
        <div className="flex items-center space-x-4">
          {/* Status indicators could go here */}
          <div className="h-2 w-2 bg-green-500 rounded-full"></div>
          <span className="text-sm text-gray-500">System Ready</span>
        </div>
      </header>

      <main className="container mx-auto px-4 py-12 flex flex-col items-center">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-medium text-gray-900 mb-2">
            How can I help you today?
          </h1>
          <p className="text-gray-500 text-lg">
            Upload documents and ask questions powered by RAG
          </p>
        </div>

        <SearchBar onSearch={handleSearch} isLoading={isLoading} />

        <UploadArea onUpload={handleUpload} isUploading={isUploading} />

        <div className="w-full border-t border-gray-100 my-8"></div>

        <Results response={response} chunks={chunks} />
      </main>
    </div>
  );
}

export default App;
