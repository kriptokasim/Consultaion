import * as Sentry from "@sentry/nextjs";

const serverDsn = process.env.SENTRY_DSN || process.env.NEXT_PUBLIC_SENTRY_DSN;

export function register() {
  if (!serverDsn) {
    return;
  }
  Sentry.init({
    dsn: serverDsn,
    environment: process.env.SENTRY_ENV || process.env.NODE_ENV || "local",
    tracesSampleRate: parseFloat(process.env.SENTRY_SAMPLE_RATE || "0.1"),
  });
}

type RequestContext = {
  params?: Record<string, string>;
  path?: string;
  routeKind?: string;
  routeType?: string;
};

export async function onRequestError(error: unknown, request: Request, context: RequestContext = {}) {
  if (!serverDsn) return;
  const url = new URL(request.url);
  const headers: Record<string, string> = {};
  request.headers.forEach((value, key) => {
    headers[key] = value;
  });
  Sentry.captureRequestError(
    error,
    {
      path: context.path || url.pathname,
      method: request.method,
      headers,
    },
    {
      routerKind: context.routeKind || "app",
      routePath: context.path || url.pathname,
      routeType: context.routeType || "app",
    },
  );
}
