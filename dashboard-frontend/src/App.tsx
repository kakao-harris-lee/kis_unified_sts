import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom';
import Cockpit from './pages/Cockpit';
import Positions from './pages/Positions';
import Signals from './pages/Signals';
import StrategyBuilder from './pages/StrategyBuilder';
import Trades from './pages/Trades';
import ErrorBoundary from './components/ErrorBoundary';
import { AssetClassProvider } from './contexts/AssetClassContext';
import { useWebSocketInvalidation } from './hooks/useWebSocket';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5000,
      gcTime: 120000,
      retry: 1,
      retryDelay: (n) => Math.min(1000 * 2 ** n, 30000),
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 1,
      retryDelay: 1000,
    },
  },
});

const navClassName = ({ isActive }: { isActive: boolean }) =>
  isActive
    ? "px-3 py-2 rounded-md bg-blue-600 text-white"
    : "px-3 py-2 rounded-md hover:bg-gray-700";

function AppInner() {
  // Must be inside QueryClientProvider — uses useQueryClient.
  useWebSocketInvalidation();

  return (
    <BrowserRouter>
      <AssetClassProvider>
        <div className="min-h-screen bg-gray-900 text-white">
          <nav className="bg-gray-800 border-b border-gray-700">
            <div className="max-w-7xl mx-auto px-4">
              <div className="flex items-center justify-between h-16">
                <div className="flex items-center space-x-8">
                  <span className="text-xl font-bold text-blue-400">
                    KIS Trading
                  </span>
                  <div className="flex space-x-4">
                    <NavLink to="/" end className={navClassName}>
                      Cockpit
                    </NavLink>
                    <NavLink to="/positions" className={navClassName}>
                      Positions
                    </NavLink>
                    <NavLink to="/signals" className={navClassName}>
                      Signals
                    </NavLink>
                    <NavLink to="/strategy-builder" className={navClassName}>
                      Strategy Builder
                    </NavLink>
                    <NavLink to="/trades" className={navClassName}>
                      Trades
                    </NavLink>
                  </div>
                </div>
              </div>
            </div>
          </nav>

          <main className="max-w-7xl mx-auto px-4 py-8">
            <Routes>
              <Route path="/" element={<Cockpit />} />
              <Route path="/cockpit" element={<Navigate to="/" replace />} />
              <Route path="/dashboard" element={<Navigate to="/" replace />} />
              <Route path="/positions" element={<Positions />} />
              <Route path="/signals" element={<Signals />} />
              <Route path="/strategy-builder" element={<StrategyBuilder />} />
              <Route path="/strategy-lab" element={<Navigate to="/strategy-builder" replace />} />
              <Route path="/trades" element={<Trades />} />
            </Routes>
          </main>
        </div>
      </AssetClassProvider>
    </BrowserRouter>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ErrorBoundary onReset={() => queryClient.clear()}>
        <AppInner />
      </ErrorBoundary>
    </QueryClientProvider>
  );
}

export default App;
