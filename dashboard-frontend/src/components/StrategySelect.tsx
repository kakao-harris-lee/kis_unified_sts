import useStrategies from '../hooks/useStrategies';

interface StrategySelectProps {
  value: string;
  onChange: (value: string) => void;
  assetClass?: string;
  allOption?: boolean;
  className?: string;
}

function StrategySelect({
  value,
  onChange,
  assetClass,
  allOption = true,
  className = 'bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm',
}: StrategySelectProps) {
  const { strategies, byAssetClass } = useStrategies();

  const filtered = assetClass ? byAssetClass(assetClass) : strategies;

  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className={className}>
      {allOption && <option value="">All Strategies</option>}
      {filtered.map((s) => (
        <option key={`${s.asset_class}/${s.name}`} value={s.name}>
          {s.name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
          {!assetClass && ` (${s.asset_class})`}
        </option>
      ))}
    </select>
  );
}

export default StrategySelect;
