type StatCardVariant = 'positive' | 'negative' | 'neutral';

const VARIANT_CLASSES: Record<StatCardVariant, string> = {
  positive: 'text-green-400',
  negative: 'text-red-400',
  neutral: 'text-white',
};

interface StatCardProps {
  title: string;
  value: string | number;
  loading?: boolean;
  /** @deprecated Use `variant` instead */
  highlight?: boolean;
  variant?: StatCardVariant;
  error?: string;
  onRetry?: () => void;
}

function StatCard({ title, value, loading, highlight, variant, error, onRetry }: StatCardProps) {
  const resolvedVariant: StatCardVariant = variant ?? (highlight ? 'positive' : 'neutral');

  return (
    <div className="bg-white rounded-lg p-4 border border-slate-200">
      <div className="text-sm text-slate-500 mb-1">{title}</div>
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
          <div className="h-8 bg-slate-100 rounded animate-pulse" />
          <div className="h-2 w-3/4 bg-slate-100/60 rounded animate-pulse" />
        </div>
      ) : (
        <div
          className={`text-2xl font-bold ${VARIANT_CLASSES[resolvedVariant]}`}
        >
          {value}
        </div>
      )}
    </div>
  );
}

export default StatCard;
