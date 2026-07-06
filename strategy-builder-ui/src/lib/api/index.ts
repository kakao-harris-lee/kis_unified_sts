/**
 * API Module Exports
 */

// Client
export {
  apiGet,
  apiPost,
  apiPut,
  apiDelete,
  ApiError,
  API_BASE,
  type ApiResponse,
  type LogEntry,
} from "./client";

// Auth
export {
  login,
  getAuthStatus,
  logout,
  switchMode,
} from "./auth";

// Symbols
export {
  searchSymbols,
  getMasterStatus,
  collectMasterFiles,
} from "./symbols";

// Account
export {
  getAccountInfo,
  getHoldings,
  getBalance,
  getBuyableAmount,
} from "./account";

// Strategies
export {
  listStrategies,
  listKisBuilderPresets,
  listCustomStrategies,
  executeStrategy,
  buildStrategy,
  previewStrategy,
  previewCodeFromState,
  registerPaperStrategy,
  listRegisteredStrategies,
  setRegisteredEnabled,
  unregisterStrategy,
  getRegisteredActivity,
  type StrategiesListResponse,
  type BuildRequest,
  type BuildResponse,
  type PreviewResponse,
  type PreviewCodeResponse,
  type RegisteredStrategy,
  type RegisteredListResponse,
  type RegisterPaperRequest,
  type StrategyActivity,
  type ActivityResponse,
} from "./strategies";

// Orders
export {
  executeOrder,
  getOrdersAccount,
  clearAccountCache,
  getPendingOrders,
  cancelOrder,
  type OrderResponse,
  type AccountInfo as OrdersAccountInfo,
  type HoldingItem,
  type PendingOrder,
  type PendingOrdersResponse,
  type CancelOrderRequest,
  type CancelOrderResponse,
} from "./orders";

// Market
export {
  getOrderbook,
  getCurrentPrice,
  type OrderbookData,
  type OrderbookResponse,
  type PriceData,
  type PriceResponse,
} from "./market";
