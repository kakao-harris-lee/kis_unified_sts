-- V4__rl_trades_ttl_5year.sql
-- Phase 5 Gate-2 prep: extend kospi.rl_trades retention from 180 days to 5 years
-- to match kospi.order_fills (V3) and satisfy futures-legal-review.md §5
-- audit-trail requirements.
--
-- Idempotent: ALTER TABLE ... MODIFY TTL is a no-op when the existing TTL
-- already equals the new expression on most ClickHouse versions; this script
-- still aligns the table to the canonical 5-year retention regardless of the
-- original CREATE TABLE TTL (180 DAY) used in shared/db/client.py prior to
-- this migration.
--
-- Spec: docs/runbooks/futures-legal-review.md §5
ALTER TABLE kospi.rl_trades
    MODIFY TTL exit_date + INTERVAL 5 YEAR;
