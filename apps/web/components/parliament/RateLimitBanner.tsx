'use client'

import React from "react";

type Props = {
  detail: string;
  resetAt?: string;
  actions?: React.ReactNode;
};

export default function RateLimitBanner({ detail, resetAt, actions }: Props) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-3xl border border-rose-200 bg-rose-50/80 p-4 text-sm text-rose-900 shadow-sm">
      <div>
        <p className="font-semibold">Rate limit reached</p>
        <p className="mt-1 text-rose-800">{detail}</p>
        {resetAt ? (
          <p className="mt-1 text-xs uppercase tracking-wide text-rose-700">
            Resets around {new Date(resetAt).toLocaleTimeString()}
          </p>
        ) : null}
      </div>
      {actions}
    </div>
  );
}
