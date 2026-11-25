"use client";

import { AlertTriangle, Ban, Check, CircleHelp, Minus } from 'lucide-react';
import type { ReactNode } from 'react';

// The page's whole colour and shape vocabulary, in one file.
//
// Two rules it exists to enforce.
//
// * **Colour never carries a fact alone.** Every mark below pairs its hue with
//   an icon AND a word, so the page reads the same in greyscale, at a glance,
//   and to anyone who cannot separate the hues.
// * **The profit/loss hues are reserved for price.** `--color-profit` is red
//   and `--color-loss` is blue here (Korean convention), so a red number on
//   this page must only ever mean «올랐다» — never «문제». Pass/fail and health
//   therefore use a different set: emerald for met, amber for attention, rose
//   for blocked.

export type Tone = 'good' | 'warn' | 'alarm' | 'neutral' | 'info';

const TONE_CLASSES: Record<Tone, string> = {
  good: 'border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-100',
  warn: 'border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100',
  alarm: 'border-rose-300 bg-rose-50 text-rose-900 dark:border-rose-800 dark:bg-rose-950 dark:text-rose-100',
  neutral: 'border-slate-300 bg-slate-50 text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200',
  info: 'border-sky-300 bg-sky-50 text-sky-900 dark:border-sky-800 dark:bg-sky-950 dark:text-sky-100',
};

/** A named chip. The text is the fact; the tone only reinforces it. */
export function Badge({
  tone = 'neutral',
  children,
  title,
}: {
  tone?: Tone;
  children: ReactNode;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs ${TONE_CLASSES[tone]}`}
    >
      {children}
    </span>
  );
}

/**
 * Whether one condition held, as icon + word + hue.
 *
 * `null` is NOT rendered as a failure: a bar the engine never judged has no
 * answer, and «미충족» would be a claim the document does not make.
 */
export function PassMark({ passed }: { passed: boolean | null }) {
  if (passed == null) {
    return (
      <span className="inline-flex items-center gap-1 text-slate-500 dark:text-slate-400">
        <CircleHelp aria-hidden="true" className="h-3.5 w-3.5" />
        알 수 없음
      </span>
    );
  }
  return passed ? (
    <span className="inline-flex items-center gap-1 font-medium text-emerald-700 dark:text-emerald-300">
      <Check aria-hidden="true" className="h-3.5 w-3.5" />
      충족
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-amber-700 dark:text-amber-300">
      <Minus aria-hidden="true" className="h-3.5 w-3.5" />
      미충족
    </span>
  );
}

/** A kernel gate that stopped a decided bar — the one alarm shape on the page. */
export function GateMark({ label, code }: { label: string; code: string }) {
  return (
    <Badge tone="alarm" title={code}>
      <Ban aria-hidden="true" className="h-3.5 w-3.5" />
      {label}
    </Badge>
  );
}

/** Something the operator should look at, short of an alarm. */
export function AttentionMark({ children }: { children: ReactNode }) {
  return (
    <Badge tone="warn">
      <AlertTriangle aria-hidden="true" className="h-3.5 w-3.5" />
      {children}
    </Badge>
  );
}

/**
 * The as-of line every card and section carries.
 *
 * Phase 1 renders only documents written in the past — a projection poll, a
 * symbols export at session end, a bars document written once. Without this
 * line on each one, a session that ended yesterday and a session running now
 * look identical, which is the single way this page could mislead.
 */
export function AsOf({ children }: { children: ReactNode }) {
  return <p className="text-xs text-slate-500 dark:text-slate-400">{children}</p>;
}

/** Seconds since export, as the banners word it. */
export function ageLabel(ageSeconds: number | null | undefined): string {
  if (ageSeconds == null) return '내보낸 시각 알 수 없음';
  const seconds = Math.floor(ageSeconds);
  if (seconds < 60) return `${seconds}초 전 내보냄`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}분 전 내보냄`;
  return `${Math.floor(minutes / 60)}시간 ${minutes % 60}분 전 내보냄`;
}
