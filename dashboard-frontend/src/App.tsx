import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Positions from './pages/Positions';
import Signals from './pages/Signals';
import Trades from './pages/Trades';
import Backtest from './pages/Backtest';
import ErrorBoundary from './components/ErrorBoundary';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5000,
      refetchInterval: 10000,
      retry: 3,
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    },
    mutations: {
      retry: 1,
      retryDelay: 1000,
    },
  },
});

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <div className="min-h-screen bg-gray-900 text-white">
            <nav className="bg-gray-800 border-b border-gray-700">
              <div className="max-w-7xl mx-auto px-4">
                <div className="flex items-center justify-between h-16">
                  <div className="flex items-center space-x-8">
                    <span className="text-xl font-bold text-blue-400">
                      KIS Trading
                    </span>
                    <div className="flex space-x-4">
                      <Link
                        to="/"
                        className="px-3 py-2 rounded-md hover:bg-gray-700"
                      >
                        Dashboard
                      </Link>
                      <Link
                        to="/positions"
                        className="px-3 py-2 rounded-md hover:bg-gray-700"
                      >
                        Positions
                      </Link>
                      <Link
                        to="/signals"
                        className="px-3 py-2 rounded-md hover:bg-gray-700"
                      >
                        Signals
                      </Link>
                      <Link
                        to="/trades"
                        className="px-3 py-2 rounded-md hover:bg-gray-700"
                      >
                        Trades
                      </Link>
                      <Link
                        to="/backtest"
                        className="px-3 py-2 rounded-md hover:bg-gray-700"
                      >
                        Backtest
                      </Link>
                    </div>
                  </div>
                </div>
              </div>
            </nav>

            <main className="max-w-7xl mx-auto px-4 py-8">
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/positions" element={<Positions />} />
                <Route path="/signals" element={<Signals />} />
                <Route path="/trades" element={<Trades />} />
                <Route path="/backtest" element={<Backtest />} />
              </Routes>
            </main>
          </div>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
