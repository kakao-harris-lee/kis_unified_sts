/**
 * API Client for P1 Strategy Builder
 */

// Keep empty by default so calls stay same-origin. Some Builder paths
// (/api/experiments, /api/account, ...) are rewritten by the Next.js catch-all
// proxy, which injects the auth header server-side. But Caddy routes the direct
// namespaces — /api/kis-builder/* and /api/strategies/* — straight to the
// dashboard, bypassing that proxy. Those requests carry no key and were 401ing
// (preset list, register, indicators, preview-code, ...). So we attach the same
// X-API-Key the STS-native cockpit client uses (src/lib/dashboard/client.ts).
// The key is already shipped to the browser via NEXT_PUBLIC_API_KEY, so this
// adds no new exposure; it just stops the builder calls from being rejected.
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

function buildHeaders(extra?: HeadersInit): HeadersInit {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (API_KEY) headers["X-API-Key"] = API_KEY;
  return { ...headers, ...(extra as Record<string, string> | undefined) };
}

export interface ApiResponse<T> {
  status: "success" | "error";
  data?: T;
  message?: string;
  logs?: LogEntry[];
}

export interface LogEntry {
  type: "info" | "success" | "error" | "warning";
  message: string;
  timestamp: string;
}

class ApiError extends Error {
  constructor(
    public statusCode: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorText = await response.text().catch(() => "Unknown error");
    throw new ApiError(response.status, errorText);
  }
  return response.json();
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "GET",
    headers: buildHeaders(),
  });
  return handleResponse<T>(response);
}

export async function apiPost<T>(
  path: string,
  body?: unknown
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: buildHeaders(),
    body: body ? JSON.stringify(body) : undefined,
  });
  return handleResponse<T>(response);
}

export async function apiPut<T>(
  path: string,
  body?: unknown
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: buildHeaders(),
    body: body ? JSON.stringify(body) : undefined,
  });
  return handleResponse<T>(response);
}

export async function apiDelete<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "DELETE",
    headers: buildHeaders(),
  });
  return handleResponse<T>(response);
}

/**
 * WebSocket base URL 반환.
 * - NEXT_PUBLIC_API_URL 설정 시: http→ws 변환 (dev/prod 자동 대응)
 * - 미설정 시: 동일 origin 사용
 * - Strategy Builder compatibility API는 Next server route가 proxy한다.
 */
export function getWsBase(): string {
  if (API_BASE) return API_BASE.replace(/^http/, "ws");
  // SSR has no window and never opens a socket; return same-origin ("") so the
  // browser path below is the only place a concrete ws:// URL is built.
  if (typeof window === "undefined") return "";
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}`;
}

export { ApiError, API_BASE };
