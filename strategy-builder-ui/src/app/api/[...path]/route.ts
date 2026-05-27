import { NextRequest } from "next/server";

const apiBase = process.env.KIS_BUILDER_API_BASE || "http://localhost:8001";
const apiKey = process.env.KIS_BUILDER_API_KEY || process.env.DASHBOARD_API_KEY || "";
const compatRoots = new Set([
  "strategies",
  "auth",
  "account",
  "orders",
  "market",
  "files",
  "symbols",
]);

export const dynamic = "force-dynamic";

type RouteContext = {
  params: { path?: string[] } | Promise<{ path?: string[] }>;
};

async function proxyBuilderApi(request: NextRequest, context: RouteContext): Promise<Response> {
  const { path = [] } = await context.params;
  const root = path[0];
  if (!root || !compatRoots.has(root)) {
    return Response.json({ detail: "Unsupported Strategy Builder API path" }, { status: 404 });
  }

  const target = new URL(`/api/kis-builder/${path.join("/")}`, apiBase);
  target.search = request.nextUrl.search;

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  headers.set("accept", "application/json");
  if (apiKey) headers.set("X-API-Key", apiKey);

  const body =
    request.method === "GET" || request.method === "HEAD"
      ? undefined
      : await request.arrayBuffer();

  const upstream = await fetch(target, {
    method: request.method,
    headers,
    body,
    cache: "no-store",
    redirect: "manual",
  });

  const responseHeaders = new Headers(upstream.headers);
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("content-length");
  responseHeaders.delete("transfer-encoding");

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

export async function GET(request: NextRequest, context: RouteContext): Promise<Response> {
  return proxyBuilderApi(request, context);
}

export async function POST(request: NextRequest, context: RouteContext): Promise<Response> {
  return proxyBuilderApi(request, context);
}

export async function PUT(request: NextRequest, context: RouteContext): Promise<Response> {
  return proxyBuilderApi(request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext): Promise<Response> {
  return proxyBuilderApi(request, context);
}
