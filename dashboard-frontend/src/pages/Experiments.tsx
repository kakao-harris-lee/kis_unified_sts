import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { experimentsApi } from '../api/client';
import ErrorMessage from '../components/ErrorMessage';
import TableSkeleton from '../components/TableSkeleton';

interface Experiment {
  experiment_id: string;
  name: string;
  artifact_location: string;
  lifecycle_stage: string;
  tags: Record<string, string>;
  creation_time: number;
  last_update_time: number;
}

interface ExperimentRun {
  run_id: string;
  experiment_id: string;
  status: string;
  start_time: number;
  end_time?: number;
  metrics: Record<string, number>;
  params: Record<string, string>;
  tags: Record<string, string>;
}

interface ExperimentsListResponse {
  experiments: Experiment[];
  total: number;
}

interface ExperimentRunsResponse {
  runs: ExperimentRun[];
  total: number;
}

interface BestRunResponse {
  run_id: string;
  metrics: Record<string, number>;
  params: Record<string, string>;
}

function Experiments() {
  const [selectedExperiment, setSelectedExperiment] = useState<string | null>(null);
  const [metricFilter, setMetricFilter] = useState<string>('sharpe_ratio');

  const {
    data: experiments,
    isLoading: experimentsLoading,
    error: experimentsError,
    refetch: refetchExperiments,
  } = useQuery<ExperimentsListResponse>({
    queryKey: ['experiments'],
    queryFn: () => experimentsApi.list().then((r) => r.data),
    refetchInterval: 30000,
  });

  const {
    data: runs,
    isLoading: runsLoading,
    error: runsError,
    refetch: refetchRuns,
  } = useQuery<ExperimentRunsResponse>({
    queryKey: ['experiment-runs', selectedExperiment],
    queryFn: () =>
      selectedExperiment
        ? experimentsApi.getRuns(selectedExperiment, { limit: 100 }).then((r) => r.data)
        : Promise.resolve({ runs: [], total: 0 }),
    enabled: !!selectedExperiment,
    refetchInterval: 30000,
  });

  const {
    data: bestRun,
    isLoading: bestRunLoading,
    error: bestRunError,
  } = useQuery<BestRunResponse>({
    queryKey: ['experiment-best', selectedExperiment, metricFilter],
    queryFn: () =>
      selectedExperiment
        ? experimentsApi.getBest(selectedExperiment, metricFilter).then((r) => r.data)
        : Promise.resolve({ run_id: '', metrics: {}, params: {} }),
    enabled: !!selectedExperiment,
  });

  const formatTimestamp = (timestamp: number) => {
    return new Date(timestamp).toLocaleString();
  };

  const formatMetricValue = (value: number) => {
    return typeof value === 'number' ? value.toFixed(4) : 'N/A';
  };

  // Error states
  if (experimentsError) {
    return (
      <ErrorMessage
        message={
          experimentsError instanceof Error
            ? experimentsError.message
            : 'Failed to load experiments'
        }
        onRetry={() => refetchExperiments()}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">MLflow Experiments</h1>
        <div className="text-sm text-gray-400">
          {experiments?.total || 0} experiment(s)
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Experiments List */}
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="text-lg font-medium mb-4">Experiments</h3>
          {experimentsLoading ? (
            <TableSkeleton rows={5} columns={3} />
          ) : experiments?.experiments && experiments.experiments.length > 0 ? (
            <div className="space-y-2">
              {experiments.experiments.map((exp) => (
                <div
                  key={exp.experiment_id}
                  onClick={() => setSelectedExperiment(exp.experiment_id)}
                  className={`p-3 rounded cursor-pointer transition-colors ${
                    selectedExperiment === exp.experiment_id
                      ? 'bg-blue-900/30 border border-blue-700'
                      : 'bg-gray-900/50 border border-gray-700 hover:bg-gray-900'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">{exp.name}</div>
                      <div className="text-xs text-gray-400">
                        ID: {exp.experiment_id}
                      </div>
                    </div>
                    <div className="text-xs text-gray-500">
                      {new Date(exp.last_update_time).toLocaleDateString()}
                    </div>
                  </div>
                  {exp.tags && Object.keys(exp.tags).length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {Object.entries(exp.tags)
                        .slice(0, 3)
                        .map(([key, value]) => (
                          <span
                            key={key}
                            className="text-xs bg-gray-700 px-2 py-1 rounded"
                          >
                            {key}: {value}
                          </span>
                        ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center text-gray-400 py-8">
              No experiments found
            </div>
          )}
        </div>

        {/* Best Run */}
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium">Best Run</h3>
            <select
              value={metricFilter}
              onChange={(e) => setMetricFilter(e.target.value)}
              className="bg-gray-900 border border-gray-600 rounded px-2 py-1 text-sm"
            >
              <option value="sharpe_ratio">Sharpe Ratio</option>
              <option value="total_return_pct">Total Return %</option>
              <option value="win_rate">Win Rate</option>
              <option value="max_drawdown_pct">Max Drawdown %</option>
            </select>
          </div>
          {!selectedExperiment ? (
            <div className="text-center text-gray-400 py-8">
              Select an experiment to view best run
            </div>
          ) : bestRunLoading ? (
            <div className="text-center text-gray-400 py-8">Loading...</div>
          ) : bestRunError ? (
            <div className="text-center text-red-400 py-8">
              Failed to load best run
            </div>
          ) : bestRun && Object.keys(bestRun.metrics).length > 0 ? (
            <div className="space-y-4">
              <div className="bg-gray-900/50 p-3 rounded">
                <div className="text-xs text-gray-400 mb-1">Run ID</div>
                <div className="font-mono text-sm">{bestRun.run_id}</div>
              </div>
              <div>
                <div className="text-sm font-medium mb-2">Metrics</div>
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(bestRun.metrics).map(([key, value]) => (
                    <div key={key} className="bg-gray-900/50 p-2 rounded">
                      <div className="text-xs text-gray-400">{key}</div>
                      <div className="font-medium">{formatMetricValue(value)}</div>
                    </div>
                  ))}
                </div>
              </div>
              {Object.keys(bestRun.params).length > 0 && (
                <div>
                  <div className="text-sm font-medium mb-2">Parameters</div>
                  <div className="bg-gray-900/50 p-3 rounded space-y-1">
                    {Object.entries(bestRun.params).map(([key, value]) => (
                      <div key={key} className="flex justify-between text-sm">
                        <span className="text-gray-400">{key}:</span>
                        <span className="font-mono">{value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center text-gray-400 py-8">
              No runs found for this experiment
            </div>
          )}
        </div>
      </div>

      {/* Runs Table */}
      {selectedExperiment && (
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium">Runs</h3>
            {runsError && (
              <button
                onClick={() => refetchRuns()}
                className="text-sm text-blue-400 hover:text-blue-300"
              >
                Retry
              </button>
            )}
          </div>
          {runsLoading ? (
            <TableSkeleton rows={5} columns={6} />
          ) : runsError ? (
            <ErrorMessage
              message={
                runsError instanceof Error
                  ? runsError.message
                  : 'Failed to load runs'
              }
              onRetry={() => refetchRuns()}
            />
          ) : runs?.runs && runs.runs.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-gray-400 border-b border-gray-700">
                  <tr>
                    <th className="text-left py-2 px-3">Run ID</th>
                    <th className="text-left py-2 px-3">Status</th>
                    <th className="text-left py-2 px-3">Start Time</th>
                    <th className="text-right py-2 px-3">Sharpe</th>
                    <th className="text-right py-2 px-3">Return %</th>
                    <th className="text-right py-2 px-3">Win Rate</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700">
                  {runs.runs.map((run) => (
                    <tr key={run.run_id} className="hover:bg-gray-900/50">
                      <td className="py-2 px-3 font-mono text-xs">
                        {run.run_id.slice(0, 8)}...
                      </td>
                      <td className="py-2 px-3">
                        <span
                          className={`px-2 py-1 rounded text-xs ${
                            run.status === 'FINISHED'
                              ? 'bg-green-900/30 text-green-400'
                              : run.status === 'RUNNING'
                              ? 'bg-blue-900/30 text-blue-400'
                              : 'bg-red-900/30 text-red-400'
                          }`}
                        >
                          {run.status}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-gray-400">
                        {formatTimestamp(run.start_time)}
                      </td>
                      <td className="py-2 px-3 text-right font-mono">
                        {run.metrics.sharpe_ratio
                          ? formatMetricValue(run.metrics.sharpe_ratio)
                          : '-'}
                      </td>
                      <td className="py-2 px-3 text-right font-mono">
                        {run.metrics.total_return_pct
                          ? formatMetricValue(run.metrics.total_return_pct)
                          : '-'}
                      </td>
                      <td className="py-2 px-3 text-right font-mono">
                        {run.metrics.win_rate
                          ? formatMetricValue(run.metrics.win_rate)
                          : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center text-gray-400 py-8">
              No runs found for this experiment
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default Experiments;
