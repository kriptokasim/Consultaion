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
    <main className="flex min-h-screen items-center justify-center bg-gradient-to-b from-amber-50 to-white p-6 text-center dark:from-stone-900 dark:to-stone-950">
      <div className="max-w-md rounded-3xl border border-stone-200 bg-white/90 p-8 shadow-xl dark:border-stone-800 dark:bg-stone-900/90">
        <main id="main" className="flex h-full items-center justify-center p-6 bg-transparent">
          <div className="space-y-3 rounded-3xl border border-amber-200/70 bg-white p-6 text-center shadow-sm dark:border-amber-900/50 dark:bg-stone-900">
            <h2 className="text-xl font-semibold text-stone-900 dark:text-white">{t("analytics.empty.overviewTitle")}</h2>
            <p className="text-sm text-stone-600 dark:text-stone-400">{t("analytics.empty.overviewDescription")}</p>
            The team has been notified. You can try again or return to the previous page.
          </p>
          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-center">
            <button
              className="rounded-full bg-amber-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-amber-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-600"
            >
              Try again
            </button>
            <a
              href="/"
              className="rounded-full border border-stone-300 px-4 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-600 dark:border-stone-700 dark:text-stone-300 dark:hover:bg-stone-800"
            >
              Go home
            </a>
          </div>
      </div>
    </main>
  );
}
