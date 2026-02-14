"use client";

import { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";


type GoogleButtonProps = {
  nextPath?: string;
  label?: string;
  className?: string;
} & ButtonHTMLAttributes<HTMLButtonElement>;

export default function GoogleButton({ nextPath = "/dashboard", label = "Continue with Google", className, ...props }: GoogleButtonProps) {
  const handleClick = () => {
    // Patchset 105: Use relative path to ensure we stay on same origin (web.consultaion.com)
    // and let Next.js rewrite handle the proxy to backend.
    const target = `/api/auth/google/login?next=${encodeURIComponent(nextPath)}`;
    if (typeof window !== "undefined") {
      window.location.href = target;
    }
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg border border-stone-200 bg-white px-4 py-2 text-sm font-semibold text-stone-800 shadow-sm transition hover:-translate-y-[1px] hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2",
        className,
      )}
      {...props}
    >
      <GoogleGlyph />
      <span>{label}</span>
    </button>
  );
}

function GoogleGlyph() {
  return (
    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M17.64 9.20454C17.64 8.56636 17.5827 7.95272 17.4763 7.36363H9V10.8454H13.8436C13.635 11.97 13.0009 12.9231 12.0477 13.5613V15.8195H14.9563C16.6581 14.2527 17.64 11.9454 17.64 9.20454Z" fill="#4285F4" />
      <path d="M9 18C11.43 18 13.4672 17.1941 14.9563 15.8195L12.0477 13.5613C11.2436 14.1013 10.215 14.4204 9 14.4204C6.65586 14.4204 4.67181 12.8372 3.96409 10.71H0.957275V13.0418C2.43817 15.9831 5.48181 18 9 18Z" fill="#34A853" />
      <path d="M3.96408 10.71C3.78408 10.17 3.68181 9.59316 3.68181 9C3.68181 8.40684 3.78408 7.83 3.96408 7.29V4.95818H0.957273C0.347727 6.17318 0 7.54772 0 9C0 10.4523 0.347727 11.8268 0.957273 13.0418L3.96408 10.71Z" fill="#FBBC05" />
      <path d="M9 3.57955C10.3232 3.57955 11.5036 4.03364 12.4309 4.92409L15.0218 2.33318C13.4632 0.883636 11.4263 0 9 0C5.48181 0 2.43817 2.01682 0.957275 4.95818L3.96409 7.29C4.67181 5.16273 6.65586 3.57955 9 3.57955Z" fill="#EA4335" />
    </svg>
  );
}
