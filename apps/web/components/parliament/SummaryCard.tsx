import type { ReactNode } from "react";

interface SummaryCardProps {
  title: string;
  description?: string;
  children: ReactNode;
}

export default function SummaryCard({ title, description, children }: SummaryCardProps) {
  return (
    <section className="rounded-3xl border border-stone-200 bg-white p-6 shadow-sm">
      <header className="mb-4 space-y-1">
        <h3 className="text-lg font-semibold text-stone-900">{title}</h3>
        {description ? <p className="text-sm text-stone-500">{description}</p> : null}
      </header>
      <div>{children}</div>
    </section>
  );
}
