import * as Sentry from "@sentry/nextjs";

const clientDsn = process.env.NEXT_PUBLIC_SENTRY_DSN || process.env.SENTRY_DSN;

export function register() {
  if (!clientDsn) {
    return;
  }
  Sentry.init({
    dsn: clientDsn,
    environment: process.env.SENTRY_ENV || process.env.NODE_ENV || "local",
    tracesSampleRate: parseFloat(
      process.env.NEXT_PUBLIC_SENTRY_SAMPLE_RATE || process.env.SENTRY_SAMPLE_RATE || "0.1",
    ),
  });
}
