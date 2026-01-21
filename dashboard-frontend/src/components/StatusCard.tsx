interface StatusCardProps {
  title: string;
  value: string;
  status?: 'success' | 'warning' | 'error' | 'neutral';
  loading?: boolean;
}

function StatusCard({ title, value, status = 'neutral', loading }: StatusCardProps) {
  const statusColors = {
    success: 'text-green-400',
    warning: 'text-yellow-400',
    error: 'text-red-400',
    neutral: 'text-gray-300',
  };

  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <div className="text-sm text-gray-400 mb-1">{title}</div>
      {loading ? (
        <div className="h-8 bg-gray-700 rounded animate-pulse" />
      ) : (
        <div className={`text-2xl font-bold ${statusColors[status]}`}>
          {value}
        </div>
      )}
    </div>
  );
}

export default StatusCard;
