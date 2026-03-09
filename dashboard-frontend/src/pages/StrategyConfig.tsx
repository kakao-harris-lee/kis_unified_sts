import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { strategiesApi } from '../api/client';
import ErrorMessage from '../components/ErrorMessage';
import TableSkeleton from '../components/TableSkeleton';

interface StrategyInfo {
  name: string;
  asset_class: string;
  entry_type: string;
  exit_type: string;
  position_type: string;
  enabled: boolean;
  description?: string;
}

interface StrategyListResponse {
  strategies: StrategyInfo[];
  total: number;
}

interface StrategyConfig {
  strategy: {
    name: string;
    asset_class: string;
    enabled: boolean;
    description?: string;
    entry: {
      type: string;
      params: Record<string, unknown>;
    };
    exit: {
      type: string;
      params: Record<string, unknown>;
    };
    position: {
      type: string;
      params: Record<string, unknown>;
    };
  };
}

function StrategyConfig() {
  const navigate = useNavigate();
  const [assetFilter, setAssetFilter] = useState<'all' | 'stock' | 'futures'>('all');
  const [selectedStrategy, setSelectedStrategy] = useState<StrategyInfo | null>(null);

  const {
    data: strategies,
    isLoading: strategiesLoading,
    error: strategiesError,
    refetch: refetchStrategies,
  } = useQuery<StrategyListResponse>({
    queryKey: ['strategies', assetFilter],
    queryFn: () =>
      strategiesApi
        .list(assetFilter === 'all' ? {} : { asset_class: assetFilter })
        .then((r) => r.data),
    refetchInterval: 30000,
  });

  const {
    data: strategyConfig,
    isLoading: configLoading,
    error: configError,
  } = useQuery<StrategyConfig>({
    queryKey: ['strategy-config', selectedStrategy?.asset_class, selectedStrategy?.name],
    queryFn: () =>
      selectedStrategy
        ? strategiesApi
            .get(selectedStrategy.asset_class, selectedStrategy.name)
            .then((r) => r.data)
        : Promise.resolve({
            strategy: {
              name: '',
              asset_class: '',
              enabled: false,
              entry: { type: '', params: {} },
              exit: { type: '', params: {} },
              position: { type: '', params: {} },
            },
          }),
    enabled: !!selectedStrategy,
  });

  const handleCreateNew = () => {
    navigate('/strategies/new');
  };

  const formatParamValue = (value: unknown): string => {
    if (typeof value === 'object' && value !== null) {
      return JSON.stringify(value, null, 2);
    }
    return String(value);
  };

  // Error states
  if (strategiesError) {
    return (
      <ErrorMessage
        message={
          strategiesError instanceof Error
            ? strategiesError.message
            : 'Failed to load strategies'
        }
        onRetry={() => refetchStrategies()}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Strategy Configuration</h1>
        <button
          onClick={handleCreateNew}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded transition-colors"
        >
          Create New Strategy
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Strategy List */}
        <div className="lg:col-span-1 bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium">Strategies</h3>
            <select
              value={assetFilter}
              onChange={(e) => setAssetFilter(e.target.value as 'all' | 'stock' | 'futures')}
              className="bg-gray-900 border border-gray-600 rounded px-2 py-1 text-sm"
            >
              <option value="all">All Assets</option>
              <option value="stock">Stock</option>
              <option value="futures">Futures</option>
            </select>
          </div>

          {strategiesLoading ? (
            <TableSkeleton rows={5} columns={1} />
          ) : strategies?.strategies && strategies.strategies.length > 0 ? (
            <div className="space-y-2">
              {strategies.strategies.map((strategy) => (
                <div
                  key={`${strategy.asset_class}-${strategy.name}`}
                  onClick={() => setSelectedStrategy(strategy)}
                  className={`p-3 rounded cursor-pointer transition-colors ${
                    selectedStrategy?.name === strategy.name &&
                    selectedStrategy?.asset_class === strategy.asset_class
                      ? 'bg-blue-900/30 border border-blue-700'
                      : 'bg-gray-900/50 border border-gray-700 hover:bg-gray-900'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="font-medium">{strategy.name}</div>
                      <div className="text-xs text-gray-400 mt-1">
                        {strategy.asset_class.toUpperCase()}
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-1">
                      <span
                        className={`px-2 py-1 rounded text-xs ${
                          strategy.enabled
                            ? 'bg-green-900/30 text-green-400'
                            : 'bg-gray-700 text-gray-400'
                        }`}
                      >
                        {strategy.enabled ? 'Enabled' : 'Disabled'}
                      </span>
                    </div>
                  </div>
                  <div className="mt-2 text-xs space-y-1">
                    <div className="text-gray-500">
                      Entry: <span className="text-gray-400">{strategy.entry_type}</span>
                    </div>
                    <div className="text-gray-500">
                      Exit: <span className="text-gray-400">{strategy.exit_type}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center text-gray-400 py-8">No strategies found</div>
          )}
        </div>

        {/* Strategy Details */}
        <div className="lg:col-span-2 space-y-4">
          {!selectedStrategy ? (
            <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
              <div className="text-center text-gray-400 py-8">
                Select a strategy to view details or click "Create New Strategy"
              </div>
            </div>
          ) : configLoading ? (
            <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
              <TableSkeleton rows={5} columns={2} />
            </div>
          ) : configError ? (
            <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
              <ErrorMessage
                message={
                  configError instanceof Error
                    ? configError.message
                    : 'Failed to load strategy configuration'
                }
                onRetry={() => {}}
              />
            </div>
          ) : strategyConfig ? (
            <>
              {/* Basic Info */}
              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-medium">Strategy Details</h3>
                  <div className="flex gap-2">
                    <button className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-1 rounded text-sm transition-colors">
                      Edit
                    </button>
                    <button className="bg-red-600 hover:bg-red-700 text-white px-3 py-1 rounded text-sm transition-colors">
                      Delete
                    </button>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-sm text-gray-400 mb-1">Name</div>
                    <div className="font-medium">{strategyConfig.strategy.name}</div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-400 mb-1">Asset Class</div>
                    <div className="font-medium">
                      {strategyConfig.strategy.asset_class.toUpperCase()}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-400 mb-1">Status</div>
                    <div>
                      <span
                        className={`px-2 py-1 rounded text-xs ${
                          strategyConfig.strategy.enabled
                            ? 'bg-green-900/30 text-green-400'
                            : 'bg-gray-700 text-gray-400'
                        }`}
                      >
                        {strategyConfig.strategy.enabled ? 'Enabled' : 'Disabled'}
                      </span>
                    </div>
                  </div>
                  {strategyConfig.strategy.description && (
                    <div className="col-span-2">
                      <div className="text-sm text-gray-400 mb-1">Description</div>
                      <div className="text-gray-300">
                        {strategyConfig.strategy.description}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Entry Configuration */}
              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-lg font-medium mb-4">Entry Configuration</h3>
                <div className="mb-4">
                  <div className="text-sm text-gray-400 mb-1">Type</div>
                  <div className="font-medium">{strategyConfig.strategy.entry.type}</div>
                </div>
                <div>
                  <div className="text-sm text-gray-400 mb-2">Parameters</div>
                  <div className="bg-gray-900/50 rounded p-4 space-y-2">
                    {Object.entries(strategyConfig.strategy.entry.params).length > 0 ? (
                      Object.entries(strategyConfig.strategy.entry.params).map(
                        ([key, value]) => (
                          <div
                            key={key}
                            className="flex justify-between text-sm border-b border-gray-800 pb-2"
                          >
                            <span className="text-gray-400">{key}:</span>
                            <span className="font-mono text-gray-300 text-right ml-4">
                              {formatParamValue(value)}
                            </span>
                          </div>
                        )
                      )
                    ) : (
                      <div className="text-center text-gray-500 py-2">
                        No parameters configured
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Exit Configuration */}
              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-lg font-medium mb-4">Exit Configuration</h3>
                <div className="mb-4">
                  <div className="text-sm text-gray-400 mb-1">Type</div>
                  <div className="font-medium">{strategyConfig.strategy.exit.type}</div>
                </div>
                <div>
                  <div className="text-sm text-gray-400 mb-2">Parameters</div>
                  <div className="bg-gray-900/50 rounded p-4 space-y-2">
                    {Object.entries(strategyConfig.strategy.exit.params).length > 0 ? (
                      Object.entries(strategyConfig.strategy.exit.params).map(
                        ([key, value]) => (
                          <div
                            key={key}
                            className="flex justify-between text-sm border-b border-gray-800 pb-2"
                          >
                            <span className="text-gray-400">{key}:</span>
                            <span className="font-mono text-gray-300 text-right ml-4">
                              {formatParamValue(value)}
                            </span>
                          </div>
                        )
                      )
                    ) : (
                      <div className="text-center text-gray-500 py-2">
                        No parameters configured
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Position Configuration */}
              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-lg font-medium mb-4">Position Configuration</h3>
                <div className="mb-4">
                  <div className="text-sm text-gray-400 mb-1">Type</div>
                  <div className="font-medium">
                    {strategyConfig.strategy.position.type}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-400 mb-2">Parameters</div>
                  <div className="bg-gray-900/50 rounded p-4 space-y-2">
                    {Object.entries(strategyConfig.strategy.position.params).length > 0 ? (
                      Object.entries(strategyConfig.strategy.position.params).map(
                        ([key, value]) => (
                          <div
                            key={key}
                            className="flex justify-between text-sm border-b border-gray-800 pb-2"
                          >
                            <span className="text-gray-400">{key}:</span>
                            <span className="font-mono text-gray-300 text-right ml-4">
                              {formatParamValue(value)}
                            </span>
                          </div>
                        )
                      )
                    ) : (
                      <div className="text-center text-gray-500 py-2">
                        No parameters configured
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export default StrategyConfig;
