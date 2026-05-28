import { useEffect, useState } from 'react';

interface RefreshIndicatorProps {
  lastUpdated: Date | number | null;
  isRefreshing?: boolean;
  showStaleWarning?: boolean;
  staleThresholdSeconds?: number;
}

function RefreshIndicator({
  lastUpdated,
  isRefreshing = false,
  showStaleWarning = true,
  staleThresholdSeconds = 30,
}: RefreshIndicatorProps) {
  const [timeAgo, setTimeAgo] = useState<string>('');
  const [isStale, setIsStale] = useState(false);

  useEffect(() => {
    const updateTimeAgo = () => {
      if (!lastUpdated) {
        setTimeAgo('Never');
        setIsStale(false);
        return;
      }

      const timestamp = lastUpdated instanceof Date ? lastUpdated.getTime() : lastUpdated;
      const now = Date.now();
      const diffSeconds = Math.floor((now - timestamp) / 1000);

      // Calculate stale status
      if (showStaleWarning) {
        setIsStale(diffSeconds > staleThresholdSeconds);
      }

      // Format time ago
      if (diffSeconds < 5) {
        setTimeAgo('Just now');
      } else if (diffSeconds < 60) {
        setTimeAgo(`${diffSeconds}s ago`);
      } else if (diffSeconds < 3600) {
        const minutes = Math.floor(diffSeconds / 60);
        setTimeAgo(`${minutes}m ago`);
      } else if (diffSeconds < 86400) {
        const hours = Math.floor(diffSeconds / 3600);
        setTimeAgo(`${hours}h ago`);
      } else {
        const days = Math.floor(diffSeconds / 86400);
        setTimeAgo(`${days}d ago`);
      }
    };

    updateTimeAgo();
    const interval = setInterval(updateTimeAgo, 1000);
    return () => clearInterval(interval);
  }, [lastUpdated, showStaleWarning, staleThresholdSeconds]);

  const getStatusColor = () => {
    if (isRefreshing) return 'text-blue-400';
    if (isStale) return 'text-yellow-400';
    return 'text-gray-400';
  };

  return (
    <div className="inline-flex items-center gap-2 text-sm">
      <div className="flex items-center gap-1.5">
        {isRefreshing ? (
          <svg
            className="w-4 h-4 text-blue-400 animate-spin"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
        ) : (
          <svg
            className={`w-4 h-4 ${getStatusColor()}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        )}
        <span className={getStatusColor()}>
          {isRefreshing ? 'Refreshing...' : `Updated ${timeAgo}`}
        </span>
      </div>
      {isStale && !isRefreshing && showStaleWarning && (
        <span className="px-2 py-0.5 text-xs font-medium bg-yellow-900/30 text-yellow-400 rounded border border-yellow-900/50">
          Stale
        </span>
      )}
    </div>
  );
}

export default RefreshIndicator;
