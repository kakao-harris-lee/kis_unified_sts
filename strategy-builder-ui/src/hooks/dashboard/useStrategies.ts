import { useQuery } from '@tanstack/react-query';
import { strategiesApi } from '@/lib/dashboard/api';

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

/**
 * Active (runtime-registry) strategies for one asset class, INCLUDING disabled
 * ones (enabled_only=false) so the builder's read-only panel can show which are
 * enabled. Separate query key per asset so the asset toggle re-fetches.
 */
export function useActiveStrategies(assetClass: "stock" | "futures") {
  const { data, isLoading, isError } = useQuery<StrategiesResponse>({
    queryKey: ["active-strategies", assetClass],
    queryFn: () =>
      strategiesApi
        .list({ asset_class: assetClass, enabled_only: false })
        .then((r) => r.data),
    staleTime: 60000,
  });

  return { strategies: data?.strategies ?? [], isLoading, isError };
}
