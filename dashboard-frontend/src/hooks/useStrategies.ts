import { useQuery } from '@tanstack/react-query';
import { strategiesApi } from '../api/client';

export interface StrategyInfo {
  name: string;
  asset_class: string;
  enabled: boolean;
  entry_type: string;
  exit_type: string;
  position_type: string;
  description: string;
}

interface StrategiesResponse {
  strategies: StrategyInfo[];
}

export function useStrategies() {
  const { data } = useQuery<StrategiesResponse>({
    queryKey: ['strategies-list'],
    queryFn: () => strategiesApi.list().then((r) => r.data),
    staleTime: 60000, // cache for 1 minute
  });

  const strategies = data?.strategies ?? [];

  const byAssetClass = (asset: string) =>
    strategies.filter((s) => s.asset_class === asset);

  return { strategies, byAssetClass };
}

export default useStrategies;
