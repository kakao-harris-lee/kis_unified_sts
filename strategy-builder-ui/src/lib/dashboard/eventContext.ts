import { apiClient } from './client';

export type EventContextAssetClass = 'stock' | 'futures' | 'all';

export type DiagnosticStatus =
  | 'ok'
  | 'stale'
  | 'sparse'
  | 'missing'
  | 'blocked'
  | 'error'
  | 'unknown';

export interface EventScoreSourceBreakdown {
  source: string;
  count: number | null;
  latest_score_at: string | null;
  status: DiagnosticStatus;
}

export interface EventScoreDiagnostics {
  latest_score_at: string | null;
  age_seconds: number | null;
  total_count: number | null;
  recent_count: number | null;
  sparsity_ratio: number | null;
  sparse: boolean;
  status: DiagnosticStatus;
  by_source: EventScoreSourceBreakdown[];
  by_impact_tier: Record<string, number>;
  warnings: string[];
}

export interface SourceTimelineItem {
  source: string;
  label: string;
  kind: 'news' | 'macro' | 'scoring' | 'event' | 'unknown';
  status: DiagnosticStatus;
  key: string | null;
  count: number | null;
  last_seen_at: string | null;
  age_seconds: number | null;
  details: string | null;
}

export interface SetupCEvidenceItem {
  id: string | null;
  timestamp: string | null;
  status: DiagnosticStatus;
  symbol: string | null;
  direction: string | null;
  event_id: string | null;
  event_type: string | null;
  impact_tier: number | null;
  score: number | null;
  reason: string | null;
  details: string | null;
  evidence: string[];
}

export interface SetupCReasonBucket {
  reason: string;
  count: number;
  latest_at: string | null;
}

export interface SetupCDiagnostics {
  strategy: string;
  enabled: boolean | null;
  window_minutes: number | null;
  min_impact_tier: number | null;
  last_eval_at: string | null;
  last_reject_reason: string | null;
  candidate_count: number;
  blocked_count: number;
  missing_count: number;
  candidates: SetupCEvidenceItem[];
  blocked: SetupCEvidenceItem[];
  missing_evidence: SetupCEvidenceItem[];
  blocked_reason_distribution: SetupCReasonBucket[];
  notes: string[];
}

export interface EventContextDiagnosticsResponse {
  asset_class: EventContextAssetClass;
  generated_at: string | null;
  event_scores: EventScoreDiagnostics;
  source_timeline: SourceTimelineItem[];
  setup_c: SetupCDiagnostics;
  missing_evidence: string[];
  notes: string[];
}

type UnknownRecord = Record<string, unknown>;

const EMPTY_EVENT_SCORES: EventScoreDiagnostics = {
  latest_score_at: null,
  age_seconds: null,
  total_count: null,
  recent_count: null,
  sparsity_ratio: null,
  sparse: false,
  status: 'unknown',
  by_source: [],
  by_impact_tier: {},
  warnings: [],
};

const EMPTY_SETUP_C: SetupCDiagnostics = {
  strategy: 'setup_c_event_reaction',
  enabled: null,
  window_minutes: null,
  min_impact_tier: null,
  last_eval_at: null,
  last_reject_reason: null,
  candidate_count: 0,
  blocked_count: 0,
  missing_count: 0,
  candidates: [],
  blocked: [],
  missing_evidence: [],
  blocked_reason_distribution: [],
  notes: [],
};

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function readRecord(record: UnknownRecord, keys: string[]): UnknownRecord | null {
  for (const key of keys) {
    const value = record[key];
    if (isRecord(value)) return value;
  }
  return null;
}

function readArray(record: UnknownRecord, keys: string[]): unknown[] {
  for (const key of keys) {
    const value = record[key];
    if (Array.isArray(value)) return value;
  }
  return [];
}

function readString(record: UnknownRecord, keys: string[]): string | null {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === 'string' && value.trim()) return value;
    if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  }
  return null;
}

function readNumber(record: UnknownRecord, keys: string[]): number | null {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === 'number' && Number.isFinite(value)) return value;
    if (typeof value === 'string' && value.trim()) {
      const parsed = Number(value);
      if (Number.isFinite(parsed)) return parsed;
    }
  }
  return null;
}

function readBoolean(record: UnknownRecord, keys: string[]): boolean | null {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === 'boolean') return value;
    if (typeof value === 'string') {
      const normalized = value.trim().toLowerCase();
      if (normalized === 'true') return true;
      if (normalized === 'false') return false;
    }
  }
  return null;
}

function readStringArray(record: UnknownRecord, keys: string[]): string[] {
  return readArray(record, keys)
    .map((value) => {
      if (typeof value === 'string') return value;
      if (typeof value === 'number' || typeof value === 'boolean') return String(value);
      if (isRecord(value)) {
        return readString(value, ['reason', 'name', 'source', 'details', 'message']);
      }
      return null;
    })
    .filter((value): value is string => Boolean(value));
}

function normalizeStatus(value: string | null): DiagnosticStatus {
  switch (value?.toLowerCase()) {
    case 'ok':
    case 'fresh':
    case 'healthy':
    case 'available':
    case 'active':
    case 'fired':
      return 'ok';
    case 'stale':
      return 'stale';
    case 'sparse':
    case 'low':
      return 'sparse';
    case 'missing':
    case 'not_available':
    case 'unavailable':
    case 'empty':
    case 'not_published_yet':
      return 'missing';
    case 'blocked':
    case 'reject':
    case 'rejected':
      return 'blocked';
    case 'error':
    case 'failed':
    case 'invalid':
    case 'malformed':
      return 'error';
    default:
      return 'unknown';
  }
}

function normalizeAssetClass(value: string | null): EventContextAssetClass {
  return value === 'stock' || value === 'all' ? value : 'futures';
}

function inferSourceKind(source: string): SourceTimelineItem['kind'] {
  const normalized = source.toLowerCase();
  if (normalized.includes('news')) return 'news';
  if (normalized.includes('macro')) return 'macro';
  if (normalized.includes('score') || normalized.includes('scoring')) return 'scoring';
  if (normalized.includes('event')) return 'event';
  return 'unknown';
}

function normalizeEventScoreSources(value: unknown): EventScoreSourceBreakdown[] {
  if (Array.isArray(value)) {
    return value.map((item) => {
      if (!isRecord(item)) {
        const source = String(item);
        return { source, count: null, latest_score_at: null, status: 'unknown' };
      }
      const source = readString(item, ['source', 'name', 'label']) ?? 'unknown';
      return {
        source,
        count: readNumber(item, ['count', 'score_count', 'total_count']),
        latest_score_at: readString(item, ['latest_score_at', 'latest_at', 'updated_at']),
        status: normalizeStatus(readString(item, ['status', 'state'])),
      };
    });
  }

  if (isRecord(value)) {
    return Object.entries(value).map(([source, raw]) => {
      if (typeof raw === 'number') {
        return { source, count: raw, latest_score_at: null, status: 'unknown' };
      }
      if (isRecord(raw)) {
        return {
          source,
          count: readNumber(raw, ['count', 'score_count', 'total_count']),
          latest_score_at: readString(raw, ['latest_score_at', 'latest_at', 'updated_at']),
          status: normalizeStatus(readString(raw, ['status', 'state'])),
        };
      }
      return { source, count: null, latest_score_at: null, status: 'unknown' };
    });
  }

  return [];
}

function normalizeImpactTiers(value: unknown): Record<string, number> {
  if (!isRecord(value)) return {};
  return Object.fromEntries(
    Object.entries(value)
      .map(([tier, count]) => {
        const numeric = typeof count === 'number' ? count : Number(count);
        return Number.isFinite(numeric) ? [tier, numeric] : null;
      })
      .filter((entry): entry is [string, number] => entry !== null),
  );
}

function normalizeEventScores(raw: UnknownRecord | null): EventScoreDiagnostics {
  if (!raw) return EMPTY_EVENT_SCORES;

  const total_count = readNumber(raw, [
    'total_count',
    'total_scores',
    'score_count',
    'event_score_count',
  ]);
  const recent_count = readNumber(raw, [
    'recent_count',
    'recent_scores',
    'score_count_recent',
    'score_count_24h',
  ]);
  const age_seconds = readNumber(raw, [
    'age_seconds',
    'freshness_seconds',
    'latest_age_seconds',
    'score_age_seconds',
  ]);
  const explicitSparse = readBoolean(raw, ['sparse', 'is_sparse']);
  const sparse =
    explicitSparse ??
    (normalizeStatus(readString(raw, ['status', 'state'])) === 'sparse' ||
      total_count === 0 ||
      recent_count === 0);
  const statusFromPayload = normalizeStatus(readString(raw, ['status', 'state']));
  const status =
    statusFromPayload !== 'unknown'
      ? statusFromPayload
      : sparse
        ? total_count === 0
          ? 'missing'
          : 'sparse'
        : age_seconds !== null && age_seconds > 86_400
          ? 'stale'
          : total_count !== null || recent_count !== null
            ? 'ok'
            : 'unknown';

  return {
    latest_score_at: readString(raw, [
      'latest_score_at',
      'latest_at',
      'updated_at',
      'last_seen_at',
    ]),
    age_seconds,
    total_count,
    recent_count,
    sparsity_ratio: readNumber(raw, ['sparsity_ratio', 'sparse_ratio']),
    sparse,
    status,
    by_source: normalizeEventScoreSources(raw.by_source ?? raw.sources),
    by_impact_tier: normalizeImpactTiers(raw.by_impact_tier ?? raw.impact_tiers),
    warnings: readStringArray(raw, ['warnings', 'missing_evidence', 'notes']),
  };
}

function normalizeSourceTimelineItem(value: unknown): SourceTimelineItem {
  if (!isRecord(value)) {
    const source = String(value);
    return {
      source,
      label: source,
      kind: inferSourceKind(source),
      status: 'unknown',
      key: null,
      count: null,
      last_seen_at: null,
      age_seconds: null,
      details: null,
    };
  }

  const source = readString(value, ['source', 'name', 'id']) ?? 'unknown';
  const available = readBoolean(value, ['available', 'healthy']);
  const explicitStatus = normalizeStatus(readString(value, ['status', 'state']));
  const status =
    explicitStatus !== 'unknown'
      ? explicitStatus
      : available === true
        ? 'ok'
        : available === false
          ? 'missing'
          : 'unknown';

  return {
    source,
    label: readString(value, ['label', 'title']) ?? source,
    kind: inferSourceKind(source),
    status,
    key: readString(value, ['key', 'stream', 'redis_key', 'table']),
    count: readNumber(value, ['count', 'rows', 'messages', 'score_count']),
    last_seen_at: readString(value, [
      'last_seen_at',
      'latest_at',
      'updated_at',
      'published_at',
    ]),
    age_seconds: readNumber(value, ['age_seconds', 'freshness_seconds', 'lag_seconds']),
    details: readString(value, ['details', 'detail', 'reason', 'message']),
  };
}

function normalizeEvidenceItem(
  value: unknown,
  fallbackStatus: DiagnosticStatus,
): SetupCEvidenceItem {
  if (!isRecord(value)) {
    const details = String(value);
    return {
      id: null,
      timestamp: null,
      status: fallbackStatus,
      symbol: null,
      direction: null,
      event_id: null,
      event_type: null,
      impact_tier: null,
      score: null,
      reason: details,
      details,
      evidence: [],
    };
  }

  const explicitStatus = normalizeStatus(readString(value, ['status', 'state', 'outcome']));
  const qualifiesWindow = readBoolean(value, ['qualifies_window', 'qualifies']);

  return {
    id: readString(value, ['id', 'signal_id', 'candidate_id']),
    timestamp: readString(value, ['timestamp', 'ts', 'ts_kst', 'generated_at', 'seen_at']),
    status:
      explicitStatus !== 'unknown'
        ? explicitStatus
        : qualifiesWindow === false
          ? 'missing'
          : fallbackStatus,
    symbol: readString(value, ['symbol', 'code']),
    direction: readString(value, ['direction', 'side', 'signal_direction']),
    event_id: readString(value, ['event_id']),
    event_type: readString(value, ['event_type', 'type', 'category']),
    impact_tier: readNumber(value, ['impact_tier', 'tier']),
    score: readNumber(value, ['score', 'impact_score', 'event_score']),
    reason: readString(value, ['reason', 'blocked_reason', 'reject_reason']),
    details: readString(value, ['details', 'message', 'description']),
    evidence: readStringArray(value, ['evidence', 'missing_evidence', 'reasons']),
  };
}

function normalizeReasonDistribution(value: unknown): SetupCReasonBucket[] {
  if (Array.isArray(value)) {
    const buckets: SetupCReasonBucket[] = [];
    for (const item of value) {
      if (!isRecord(item)) continue;
      const reason = readString(item, ['reason', 'blocked_reason', 'name']);
      const count = readNumber(item, ['count', 'total']);
      if (!reason || count === null) continue;
      buckets.push({
        reason,
        count,
        latest_at: readString(item, ['latest_at', 'last_seen_at', 'timestamp']),
      });
    }
    return buckets;
  }

  if (isRecord(value)) {
    const buckets: SetupCReasonBucket[] = [];
    for (const [reason, count] of Object.entries(value)) {
      const numeric = typeof count === 'number' ? count : Number(count);
      if (!Number.isFinite(numeric)) continue;
      buckets.push({ reason, count: numeric, latest_at: null });
    }
    return buckets;
  }

  return [];
}

function deriveReasonDistribution(blocked: SetupCEvidenceItem[]): SetupCReasonBucket[] {
  const buckets = new Map<string, SetupCReasonBucket>();
  for (const item of blocked) {
    const reason = item.reason ?? item.details ?? 'blocked';
    const existing = buckets.get(reason);
    if (existing) {
      existing.count += 1;
      existing.latest_at = item.timestamp ?? existing.latest_at;
    } else {
      buckets.set(reason, {
        reason,
        count: 1,
        latest_at: item.timestamp,
      });
    }
  }
  return [...buckets.values()].sort((a, b) => b.count - a.count);
}

function sumReasonDistribution(rows: SetupCReasonBucket[]): number {
  return rows.reduce((sum, row) => sum + row.count, 0);
}

function normalizeSetupC(
  raw: UnknownRecord | null,
  setupEvalRaw: UnknownRecord | null,
): SetupCDiagnostics {
  if (!raw) return EMPTY_SETUP_C;

  const candidates = readArray(raw, ['candidates', 'candidate_evidence', 'recent_events']).map(
    (item) => normalizeEvidenceItem(item, 'ok'),
  );
  const blocked = readArray(raw, ['blocked', 'blocks', 'blocked_evidence']).map((item) =>
    normalizeEvidenceItem(item, 'blocked'),
  );
  const missing_evidence = readArray(raw, [
    'missing_evidence',
    'missing',
    'missing_sources',
    'missing_event_sources',
  ]).map((item) => normalizeEvidenceItem(item, 'missing'));
  const explicitDistribution = normalizeReasonDistribution(
    raw.blocked_reason_distribution ?? raw.blocked_reasons ?? raw.reject_reasons,
  );
  const latestEvalBlocked =
    setupEvalRaw && readString(setupEvalRaw, ['outcome']) === 'reject'
      ? normalizeEvidenceItem(
          {
            reason: readString(setupEvalRaw, ['reason']),
            timestamp: readString(setupEvalRaw, ['latest_at', 'ts_kst', 'updated_at']),
            outcome: readString(setupEvalRaw, ['outcome']),
          },
          'blocked',
        )
      : null;
  const blockedRows =
    latestEvalBlocked && blocked.length === 0 ? [latestEvalBlocked] : blocked;
  const distribution =
    explicitDistribution.length > 0
      ? explicitDistribution
      : deriveReasonDistribution(blockedRows);
  const rootCause = readString(raw, ['root_cause']);

  return {
    strategy: readString(raw, ['strategy', 'name']) ?? 'setup_c_event_reaction',
    enabled: readBoolean(raw, ['enabled']),
    window_minutes: readNumber(raw, ['window_minutes', 'event_window_minutes']),
    min_impact_tier: readNumber(raw, ['min_impact_tier']),
    last_eval_at:
      readString(raw, ['last_eval_at', 'latest_eval_at', 'updated_at']) ??
      (setupEvalRaw ? readString(setupEvalRaw, ['latest_at', 'ts_kst', 'updated_at']) : null),
    last_reject_reason:
      readString(raw, ['last_reject_reason', 'latest_reject_reason']) ??
      (setupEvalRaw && readString(setupEvalRaw, ['outcome']) === 'reject'
        ? readString(setupEvalRaw, ['reason'])
        : null),
    candidate_count: readNumber(raw, ['candidate_count', 'candidates_count']) ?? candidates.length,
    blocked_count:
      readNumber(raw, ['blocked_count', 'blocks_count']) ??
      (distribution.length > 0 ? sumReasonDistribution(distribution) : blockedRows.length),
    missing_count:
      readNumber(raw, ['missing_count', 'missing_evidence_count']) ?? missing_evidence.length,
    candidates,
    blocked: blockedRows,
    missing_evidence,
    blocked_reason_distribution: distribution,
    notes: [...readStringArray(raw, ['notes', 'warnings']), ...(rootCause ? [rootCause] : [])],
  };
}

function deriveEventScoreSourcesFromTimeline(
  timeline: SourceTimelineItem[],
): EventScoreSourceBreakdown[] {
  return timeline
    .filter((item) => item.source.includes('event') || item.source.includes('scored'))
    .map((item) => ({
      source: item.label,
      count: item.count,
      latest_score_at: item.last_seen_at,
      status: item.status,
    }));
}

export function normalizeEventContextDiagnostics(
  raw: unknown,
): EventContextDiagnosticsResponse {
  const root = isRecord(raw) ? raw : {};
  const eventScoresRaw = readRecord(root, [
    'event_score',
    'event_scores',
    'event_score_freshness',
    'event_score_diagnostics',
    'scores',
  ]);
  const setupEvalRaw = readRecord(root, ['setup_eval', 'latest_setup_eval']);
  const setupRaw = readRecord(root, [
    'setup_c',
    'setup_c_diagnostics',
    'setup_c_context',
    'setup_c_root_cause',
  ]);
  const sourceTimeline = readArray(root, [
    'source_timeline',
    'news_macro_timeline',
    'sources',
    'source_status',
  ]).map(normalizeSourceTimelineItem);
  const eventScores = normalizeEventScores(eventScoresRaw);
  const normalizedEventScores =
    eventScores.by_source.length > 0
      ? eventScores
      : {
          ...eventScores,
          by_source: deriveEventScoreSourcesFromTimeline(sourceTimeline),
        };

  return {
    asset_class: normalizeAssetClass(readString(root, ['asset_class'])),
    generated_at: readString(root, ['generated_at', 'as_of', 'timestamp']),
    event_scores: normalizedEventScores,
    source_timeline: sourceTimeline,
    setup_c: normalizeSetupC(setupRaw, setupEvalRaw),
    missing_evidence: readStringArray(root, ['missing_evidence', 'warnings']),
    notes: [
      ...readStringArray(root, ['notes']),
      ...readStringArray(root, ['config_warnings']),
    ],
  };
}

export const eventContextApi = {
  getDiagnostics: (params?: { asset_class?: string }) =>
    apiClient.get<EventContextDiagnosticsResponse>('/api/event-context/diagnostics', {
      params,
    }),
};
