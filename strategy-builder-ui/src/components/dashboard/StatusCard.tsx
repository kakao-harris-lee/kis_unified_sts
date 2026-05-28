interface StatusCardProps {
  title: string;
  value: string;
  status?: 'success' | 'warning' | 'error' | 'neutral';
  loading?: boolean;
  error?: string;
  onRetry?: () => void;
}

function StatusCard({
  title,
  value,
  status = 'neutral',
  loading,
  error,
  onRetry
}: StatusCardProps) {
  const statusColors = {
    success: 'text-green-400',
    warning: 'text-yellow-400',
    error: 'text-red-400',
    neutral: 'text-slate-700',
  };

  return (
    <div className="bg-white rounded-lg p-4 border border-slate-200">
      <div className="text-sm text-slate-500 mb-1">{title}</div>

      {error ? (
        <div className="flex items-start gap-2">
          <div className="flex-shrink-0">
            <svg
              className="w-5 h-5 text-red-400 mt-0.5"
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
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs text-red-400 mb-2">{error}</div>
            {onRetry && (
              <button
                onClick={onRetry}
                className="px-2 py-1 text-xs font-medium text-white bg-red-600 hover:bg-red-700 rounded transition-colors"
              >
                Retry
              </button>
            )}
          </div>
        </div>
      ) : loading ? (
        <div className="space-y-2">
          <div className="h-8 bg-slate-100 rounded animate-pulse" />
        </div>
      ) : (
        <div className={`text-2xl font-bold ${statusColors[status]}`}>
          {value}
        </div>
      )}
    </div>
  );
}

export default StatusCard;
