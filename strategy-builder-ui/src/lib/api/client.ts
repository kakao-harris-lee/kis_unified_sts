/**
 * API Client for P1 Strategy Builder
 */

// Keep empty by default so calls stay same-origin and the Next server proxy can
// route /api/* to the STS compatibility API with server-side auth headers.
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

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
    headers: {
      "Content-Type": "application/json",
    },
  });
  return handleResponse<T>(response);
}

export async function apiPost<T>(
  path: string,
  body?: unknown
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
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
    headers: {
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  return handleResponse<T>(response);
}

export async function apiDelete<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
    },
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
