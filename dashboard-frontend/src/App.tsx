import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Positions from './pages/Positions';
import Signals from './pages/Signals';
import Trades from './pages/Trades';
import Backtest from './pages/Backtest';
import Experiments from './pages/Experiments';
import StrategyConfig from './pages/StrategyConfig';
import StrategyCreate from './pages/StrategyCreate';
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

const navClassName = ({ isActive }: { isActive: boolean }) =>
  isActive
    ? "px-3 py-2 rounded-md bg-blue-600 text-white"
    : "px-3 py-2 rounded-md hover:bg-gray-700";

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ErrorBoundary onReset={() => queryClient.clear()}>
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
                      <NavLink to="/" end className={navClassName}>
                        Dashboard
                      </NavLink>
                      <NavLink to="/positions" className={navClassName}>
                        Positions
                      </NavLink>
                      <NavLink to="/signals" className={navClassName}>
                        Signals
                      </NavLink>
                      <NavLink to="/trades" className={navClassName}>
                        Trades
                      </NavLink>
                      <NavLink to="/backtest" className={navClassName}>
                        Backtest
                      </NavLink>
                      <NavLink to="/experiments" className={navClassName}>
                        Experiments
                      </NavLink>
                      <NavLink to="/strategies" className={navClassName}>
                        Strategies
                      </NavLink>
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
                <Route path="/experiments" element={<Experiments />} />
                <Route path="/strategies" element={<StrategyConfig />} />
                <Route path="/strategies/new" element={<StrategyCreate />} />
              </Routes>
            </main>
          </div>
        </BrowserRouter>
      </ErrorBoundary>
    </QueryClientProvider>
  );
}

export default App;
