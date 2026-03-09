/**
 * Venue metrics data from ATS/KRX order routing.
 */
export interface VenueMetricsData {
  krx_count: number;
  ats_count: number;
  krx_fill_rate: number;
  ats_fill_rate: number;
  avg_price_improvement_bps: number;
  ats_price_improvement_bps: number;
}
