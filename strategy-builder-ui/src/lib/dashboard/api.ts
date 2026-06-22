// STS-native dashboard API client.
//
// Split into per-domain modules (./client + ./<domain>). This file is a thin
// re-export barrel so existing import paths (`@/lib/dashboard/api`) keep working
// for every call site. This client is SEPARATE from the upstream KIS client in
// src/lib/api/ by design — do not merge them (see strategy-builder-ui/UPSTREAM.md).
export { apiClient } from './client';
export { tradingApi } from './trading';
export { signalsApi } from './signals';
export { tradesApi } from './trades';
export { strategiesApi } from './strategies';
export { strategyLabApi } from './strategyLab';
export { strategyBuilderApi } from './strategyBuilder';
export { fillsApi } from './fills';
export { healthApi } from './health';
export { coverageApi } from './coverage';
export { eventContextApi } from './eventContext';
export { killSwitchApi } from './killSwitch';
