import { describe, expect, it } from "vitest";
import { normalizeEventContextDiagnostics } from "./eventContext";

describe("normalizeEventContextDiagnostics", () => {
  it("normalizes planned Setup C diagnostics aliases", () => {
    const normalized = normalizeEventContextDiagnostics({
      asset_class: "futures",
      as_of: "2026-06-22T10:00:00+09:00",
      event_score_freshness: {
        latest_at: "2026-06-22T09:58:00+09:00",
        freshness_seconds: 120,
        total_scores: 0,
        recent_scores: 0,
        sources: [{ name: "event_scorer", score_count: 0, state: "missing" }],
        impact_tiers: { "1": 0, "2": 0 },
        warnings: ["event_scores_empty"],
      },
      news_macro_timeline: [
        {
          name: "stream:news.raw",
          label: "Raw News",
          available: false,
          count: 0,
          redis_key: "stream:news.raw",
        },
      ],
      setup_c_diagnostics: {
        enabled: true,
        window_minutes: 720,
        min_impact_tier: 2,
        candidate_evidence: [
          {
            signal_id: "c1",
            symbol: "101V9000",
            direction: "long",
            event_id: "bok_rate",
            impact_score: 72,
          },
        ],
        blocked_evidence: [
          {
            blocked_reason: "no_breakout_within_buffer",
            ts_kst: "2026-06-22T09:35:00+09:00",
          },
        ],
        missing_sources: ["event_scores"],
      },
    });

    expect(normalized.asset_class).toBe("futures");
    expect(normalized.generated_at).toBe("2026-06-22T10:00:00+09:00");
    expect(normalized.event_scores.sparse).toBe(true);
    expect(normalized.event_scores.status).toBe("missing");
    expect(normalized.event_scores.by_source[0]).toMatchObject({
      source: "event_scorer",
      count: 0,
      status: "missing",
    });
    expect(normalized.source_timeline[0]).toMatchObject({
      source: "stream:news.raw",
      status: "missing",
      key: "stream:news.raw",
    });
    expect(normalized.setup_c.window_minutes).toBe(720);
    expect(normalized.setup_c.candidate_count).toBe(1);
    expect(normalized.setup_c.blocked_reason_distribution[0]).toMatchObject({
      reason: "no_breakout_within_buffer",
      count: 1,
    });
    expect(normalized.setup_c.missing_evidence[0].reason).toBe("event_scores");
  });

  it("normalizes current backend event-context diagnostics", () => {
    const normalized = normalizeEventContextDiagnostics({
      status: "degraded",
      asset_class: "futures",
      generated_at: "2026-06-22T01:00:00+00:00",
      event_score: {
        available: true,
        status: "fresh",
        latest_at: "2026-06-22T00:58:00+00:00",
        age_seconds: 120,
        ttl_minutes: 30,
        impact_score: 88,
        event_type: "BOK_rate_decision",
        source: "rule",
        sparse: true,
        recent_count: 1,
        missing_evidence: [],
      },
      setup_eval: {
        available: true,
        status: "ok",
        outcome: "reject",
        reason: "no_breakout_within_buffer(px=100,hi=101,lo=99,buf=1)",
        latest_at: "2026-06-22T00:59:00+00:00",
        age_seconds: 60,
      },
      source_timeline: [
        {
          name: "setup_c_latest_eval",
          kind: "redis_hash",
          key: "trading:futures:setup_eval",
          available: true,
          status: "ok",
          count: 1,
          latest_at: "2026-06-22T00:59:00+00:00",
          age_seconds: 60,
          detail: "no_breakout_within_buffer(px=100,hi=101,lo=99,buf=1)",
        },
      ],
      setup_c: {
        enabled: true,
        window_minutes: 720,
        min_impact_tier: 2,
        candidate_count: 1,
        scheduled_events_total: 1,
        scheduled_events_in_window: 1,
        blocked_reasons: {
          "no_breakout_within_buffer(px=100,hi=101,lo=99,buf=1)": 1,
        },
        missing_event_sources: ["news_scored"],
        root_cause: "setup_c_selective_breakout_or_risk",
        recent_events: [
          {
            event_id: "bok_test",
            event_type: "BOK_rate_decision",
            scheduled_at: "2026-06-22T09:00:00+09:00",
            impact_tier: 1,
            elapsed_minutes: 5,
            qualifies_window: true,
          },
        ],
      },
      missing_evidence: ["news_scored"],
      notes: ["setup_c_latest_eval is direct runtime evidence"],
    });

    expect(normalized.event_scores.latest_score_at).toBe("2026-06-22T00:58:00+00:00");
    expect(normalized.event_scores.status).toBe("ok");
    expect(normalized.setup_c.last_reject_reason).toContain("no_breakout");
    expect(normalized.setup_c.blocked_count).toBe(1);
    expect(normalized.setup_c.missing_count).toBe(1);
    expect(normalized.setup_c.candidates[0]).toMatchObject({
      event_id: "bok_test",
      event_type: "BOK_rate_decision",
      status: "ok",
    });
    expect(normalized.source_timeline[0]).toMatchObject({
      source: "setup_c_latest_eval",
      details: "no_breakout_within_buffer(px=100,hi=101,lo=99,buf=1)",
    });
  });
});
