"use client";

import { useQuery, type UseQueryOptions } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import config from '@/config/tos-control-plane.json';
import {
  barsState,
  isAcceptedBarsDocument,
  tosBarsApi,
  type BarsState,
  type TosBarsDocument,
  type TosBarsResponse,
  type TosSessionsResponse,
} from '@/lib/dashboard/tosBars';
import {
  isAcceptedStatusDocument,
  statusState,
  tosStatusApi,
  type StatusState,
  type TosStatusDocument,
  type TosStatusResponse,
} from '@/lib/dashboard/tosStatus';
import {
  isAcceptedSymbolsDocument,
  symbolsState,
  tosSymbolsApi,
  type SymbolsState,
  type TosSymbolsDocument,
  type TosSymbolsResponse,
} from '@/lib/dashboard/tosSymbols';

// The five read models of /tos behind one key per model.
//
// They are separate reads with separate freshness stories — the projection is
// polled, the symbols document is written at session end, a bars document is
// written once per session — so each keeps its own banner and never inherits
// another's absence. What this module centralises is only the key and the
// acceptance step, because two components asking for the same document with
// different keys would fetch a megabyte twice, and two components disagreeing
// about whether a document is usable would render half a page over it.

export const PROJECTION_KEY = ['tos-operator-projection'] as const;
export const STATUS_KEY = ['tos-status-board'] as const;
export const SYMBOLS_KEY = ['tos-symbols-today'] as const;
export const SESSIONS_KEY = ['tos-sessions'] as const;

/** The key a bars document is cached under. Shared by every reader of it. */
export function barsKey(session: string) {
  return ['tos-session-bars', session] as const;
}

/**
 * The options every bars reader must pass, so the cards and the panels below
 * them share one fetch per session rather than one each.
 */
export function barsQueryOptions(session: string): UseQueryOptions<TosBarsResponse> & { queryKey: readonly unknown[] } {
  return {
    queryKey: barsKey(session),
    queryFn: () => tosBarsApi.getBars(session),
    retry: false,
    // A bars document is written once, at session end. Re-reading a megabyte
    // because a component remounted would cost the operator a visible stall
    // for a document that cannot have changed.
    staleTime: config.pollIntervalMs * 4,
  };
}

function authFailed(error: unknown): boolean {
  const status = isAxiosError(error) ? error.response?.status : undefined;
  return status === 401 || status === 403;
}

export interface BarsRead {
  state: BarsState;
  document: TosBarsDocument | null;
  response: TosBarsResponse | undefined;
  authError: boolean;
  isFetching: boolean;
}

/** One session's per-bar document, already judged acceptable or not. */
export function useBarsDocument(session: string): BarsRead {
  const query = useQuery(barsQueryOptions(session));
  const response = query.data;
  const state = barsState(response, query.isError || query.fetchStatus === 'paused');
  return {
    state,
    // The same acceptance predicate the banner uses — see isAcceptedBarsDocument.
    document: response?.available && isAcceptedBarsDocument(response.document) ? response.document : null,
    response,
    authError: authFailed(query.error),
    isFetching: query.isFetching,
  };
}

export interface SymbolsRead {
  state: SymbolsState;
  document: TosSymbolsDocument | null;
  response: TosSymbolsResponse | undefined;
  authError: boolean;
}

/** Today's per-symbol operator rows. */
export function useSymbolsDocument(): SymbolsRead {
  const query = useQuery({
    queryKey: SYMBOLS_KEY,
    queryFn: tosSymbolsApi.getSymbolsToday,
    refetchInterval: config.pollIntervalMs,
    retry: false,
  });
  const response = query.data;
  return {
    state: symbolsState(response, query.isError || query.fetchStatus === 'paused'),
    document: response?.available && isAcceptedSymbolsDocument(response.document) ? response.document : null,
    response,
    authError: authFailed(query.error),
  };
}

export interface StatusRead {
  state: StatusState;
  document: TosStatusDocument | null;
  response: TosStatusResponse | undefined;
  authError: boolean;
}

/**
 * The one-page status board: what `sts tos status` judged, as a document.
 *
 * Polled on the same interval as the projection, because it is the answer to
 * «지금 괜찮은가» and it is small — the exporter writes it beside the symbols
 * document, so a board that stops being rewritten is itself the signal the
 * strip reports (its date, against the viewer's KST today).
 */
export function useStatusDocument(): StatusRead {
  const query = useQuery({
    queryKey: STATUS_KEY,
    queryFn: tosStatusApi.getStatus,
    refetchInterval: config.pollIntervalMs,
    retry: false,
  });
  const response = query.data;
  return {
    state: statusState(response, query.isError || query.fetchStatus === 'paused'),
    // The same acceptance predicate the banner uses — see isAcceptedStatusDocument.
    document: response?.available && isAcceptedStatusDocument(response.document) ? response.document : null,
    response,
    authError: authFailed(query.error),
  };
}

export interface SessionsRead {
  response: TosSessionsResponse | undefined;
  /** `available` AND a real array — a body that lost its key must not throw. */
  sessions: TosSessionsResponse['sessions'];
  truncated: boolean;
  failed: boolean;
}

/** The exported sessions, newest first, as the route ordered them. */
export function useSessionsList(): SessionsRead {
  const query = useQuery({ queryKey: SESSIONS_KEY, queryFn: tosBarsApi.listSessions, retry: false });
  const response = query.data;
  const sessions = response?.available && Array.isArray(response.sessions) ? response.sessions : [];
  return {
    response,
    sessions,
    truncated: response?.truncated === true,
    failed: query.isError || response?.available === false,
  };
}
