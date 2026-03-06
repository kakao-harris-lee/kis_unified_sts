interface StatCardProps {
  title: string;
  value: string | number;
  loading?: boolean;
  highlight?: boolean;
  error?: string;
  onRetry?: () => void;
}

function StatCard({ title, value, loading, highlight, error, onRetry }: StatCardProps) {
  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <div className="text-sm text-gray-400 mb-1">{title}</div>
      {error ? (
        <div className="flex items-start gap-2">
          <svg
            className="w-5 h-5 text-red-400 mt-0.5 flex-shrink-0"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <div className="flex-1 min-w-0">
            <div className="text-sm text-red-400">{error}</div>
            {onRetry && (
              <button
                onClick={onRetry}
                className="mt-1 px-2 py-0.5 text-xs font-medium text-white bg-red-600 hover:bg-red-700 rounded transition-colors"
              >
                Retry
              </button>
            )}
          </div>
        </div>
      ) : loading ? (
        <div className="space-y-2">
          <div className="h-8 bg-gray-700 rounded animate-pulse" />
          <div className="h-2 w-3/4 bg-gray-700/60 rounded animate-pulse" />
        </div>
      ) : (
        <div
          className={`text-2xl font-bold ${
            highlight ? 'text-green-400' : 'text-white'
          }`}
        >
          {value}
        </div>
      )}
    </div>
  );
}

export default StatCard;
