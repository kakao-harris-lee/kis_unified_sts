interface SideBadgeProps {
  side: 'BUY' | 'SELL' | 'LONG' | 'SHORT' | 'long' | 'short' | string;
}

function SideBadge({ side }: SideBadgeProps) {
  // Normalize to uppercase for comparison
  const normalizedSide = side.toUpperCase();

  // Determine if this is a buy/long (green) or sell/short (red) side
  const isGreen = normalizedSide === 'BUY' || normalizedSide === 'LONG';

  const colorClass = isGreen
    ? 'bg-green-900 text-green-300'
    : 'bg-red-900 text-red-300';

  return (
    <span className={`px-2 py-1 rounded text-xs font-medium ${colorClass}`}>
      {side}
    </span>
  );
}

export default SideBadge;
