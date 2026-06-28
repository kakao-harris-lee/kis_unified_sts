// Shared KST (Asia/Seoul) datetime formatting for the dashboard. Trading and
// session logic is KST-native, so all operator-facing timestamps render in KST
// regardless of the browser's local timezone.

const KST_TIME_ZONE = "Asia/Seoul";

/** Format a timestamp as a KST date+time string, or `fallback` when absent/invalid. */
export function formatKstDateTime(
  value?: string | number | Date | null,
  fallback = "not available",
): string {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return typeof value === "string" ? value : fallback;
  }
  return date.toLocaleString("ko-KR", {
    timeZone: KST_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Compact KST month/day + time (no year), used in dense timelines. */
export function formatKstShort(value?: string | null, fallback = "-"): string {
  if (!value) {
    return fallback;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("ko-KR", {
    timeZone: KST_TIME_ZONE,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
