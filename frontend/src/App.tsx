import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import axios from 'axios';
import { Network } from 'lucide-react';
import { Home } from './pages/Home';
import { Visualizer } from './pages/Visualizer';

axios.defaults.baseURL = import.meta.env.VITE_API_URL || `${window.location.protocol}//${window.location.hostname}:8000`;

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-full bg-paper text-ink">
        <header className="h-14 border-b border-paper-line">
          <div className="mx-auto flex h-full max-w-shell items-center justify-between px-6">
            <Link to="/" className="flex items-baseline gap-3">
              <span className="text-[15px] font-medium tracking-tight text-ink">ragcli</span>
              <span className="hidden text-[11px] text-ink-muted sm:inline">
                local retrieval over your own documents
              </span>
            </Link>
            <nav className="flex items-center gap-4">
              <Link
                to="/visualize"
                className="flex items-center gap-2 text-[13px] text-ink-secondary transition-colors duration-150 hover:text-ink"
              >
                <Network size={16} strokeWidth={1.5} className="text-ink-muted" />
                Embedding graph
              </Link>
            </nav>
          </div>
        </header>

        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/visualize" element={<Visualizer />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;
