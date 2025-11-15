'use client'

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
useEffect(() => {
    console.error("Global error boundary", error);
    if (typeof window !== "undefined" && window.Sentry) {
      window.Sentry.captureException(error);
    }
  }, [error]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-gradient-to-b from-amber-50 to-white p-6 text-center">
      <div className="max-w-md rounded-3xl border border-stone-200 bg-white/90 p-8 shadow-xl">
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-600">Something went wrong</p>
        <h1 className="mt-2 text-2xl font-semibold text-stone-900">We couldn’t load this view</h1>
        <p className="mt-3 text-sm text-stone-600">
          The team has been notified. You can try again or return to the previous page.
        </p>
        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-center">
          <button
            type="button"
            onClick={() => reset()}
            className="rounded-full bg-amber-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-amber-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-600"
          >
            Try again
          </button>
          <a
            href="/"
            className="rounded-full border border-stone-300 px-4 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-600"
          >
            Go home
          </a>
        </div>
      </div>
    </main>
  );
}
