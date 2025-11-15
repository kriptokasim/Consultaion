"use client";

import { cn } from "@/lib/utils";

type EmptyStateProps = {
  title: string;
  description?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
};

export default function EmptyState({ title, description, action, icon, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-3xl border border-dashed border-stone-200 bg-white/70 p-8 text-center",
        className,
      )}
    >
      {icon}
      <p className="text-sm font-semibold text-stone-800">{title}</p>
      {description ? <p className="max-w-sm text-xs text-stone-500">{description}</p> : null}
      {action}
    </div>
  );
}
