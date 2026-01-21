interface StatCardProps {
  title: string;
  value: string | number;
  loading?: boolean;
  highlight?: boolean;
}

function StatCard({ title, value, loading, highlight }: StatCardProps) {
  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <div className="text-sm text-gray-400 mb-1">{title}</div>
      {loading ? (
        <div className="h-8 bg-gray-700 rounded animate-pulse" />
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
