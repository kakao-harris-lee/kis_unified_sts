"use client";

// Shared chart card shell (fixed-height chart area + empty state), used by
// the /market structure charts and the /risk unified-equity charts.
export default function ChartCard({
  title,
  subtitle,
  isEmpty,
  emptyLabel = "데이터 없음 — 수집/엔진 가동 후 표시됩니다",
  children,
}: {
  title: string;
  subtitle?: string;
  isEmpty: boolean;
  emptyLabel?: string;
  children: React.ReactNode;
}) {
  return (
    <section
      aria-label={title}
      className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900"
    >
      <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
        {title}
      </h3>
      {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
      {isEmpty ? (
        <div className="flex h-64 items-center justify-center text-sm text-slate-400">
          {emptyLabel}
        </div>
      ) : (
        <div className="mt-2 h-64">{children}</div>
      )}
    </section>
  );
}
