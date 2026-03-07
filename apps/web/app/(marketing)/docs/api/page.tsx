"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n/client";
import { ArrowLeft, Copy, Check } from "lucide-react";
import { useState } from "react";

export default function ApiDocsPage() {
    const { t } = useI18n();
    const [copied, setCopied] = useState(false);

    const exampleCode = `const res = await fetch("https://api.consultaion.com/debates", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  credentials: "include",
  body: JSON.stringify({
    question: "How should we roll out AI in 2025?",
    mode: "strategy",
  }),
});

const data = await res.json();
// console.log(data);`;

    const handleCopy = () => {
        navigator.clipboard.writeText(exampleCode);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="mx-auto max-w-3xl px-6 py-12">
            <Link
                href="/docs"
                className="mb-8 inline-flex items-center gap-2 text-sm font-medium text-amber-800 hover:text-amber-600"
            >
                <ArrowLeft className="h-4 w-4" />
                {t("nav.goBack")}
            </Link>

            <h1 className="mb-4 text-4xl font-bold text-slate-900 dark:text-white">{t("docs.api.title")}</h1>
            <p className="mb-12 text-lg text-slate-600 dark:text-slate-400">{t("docs.api.description")}</p>

            <div className="space-y-12">
                <section>
                    <h2 className="mb-4 text-2xl font-semibold text-slate-900 dark:text-white">{t("docs.api.baseUrl")}</h2>
                    <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-4 font-mono text-sm text-amber-900 dark:border-amber-900/30 dark:bg-amber-900/20 dark:text-amber-200">
                        https://api.consultaion.com
                    </div>
                    <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
                        Local development: set <code className="rounded bg-amber-100 px-1 py-0.5 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">NEXT_PUBLIC_API_URL</code> in <code className="rounded bg-amber-100 px-1 py-0.5 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">.env.local</code>
                    </p>
                </section>

                <section>
                    <h2 className="mb-4 text-2xl font-semibold text-slate-900 dark:text-white">{t("docs.api.auth")}</h2>
                    <p className="text-slate-600 dark:text-slate-400">{t("docs.api.auth.description")}</p>
                </section>

                <section>
                    <h2 className="mb-4 text-2xl font-semibold text-slate-900 dark:text-white">{t("docs.api.endpoints")}</h2>
                    <div className="space-y-4">
                        <div className="rounded-lg border border-amber-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
                            <div className="flex items-center gap-3">
                                <span className="rounded bg-emerald-100 px-2 py-1 text-xs font-bold text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">POST</span>
                                <code className="text-sm font-semibold text-slate-900 dark:text-white">/debates</code>
                            </div>
                            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">Create a new debate session.</p>
                        </div>
                        <div className="rounded-lg border border-amber-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
                            <div className="flex items-center gap-3">
                                <span className="rounded bg-blue-100 px-2 py-1 text-xs font-bold text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">GET</span>
                                <code className="text-sm font-semibold text-slate-900 dark:text-white">/debates/{`{id}`}</code>
                            </div>
                            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">Retrieve debate results and history.</p>
                        </div>
                    </div>
                </section>

                <section>
                    <h2 className="mb-4 text-2xl font-semibold text-slate-900 dark:text-white">{t("docs.api.example")}</h2>
                    <div className="relative rounded-lg border border-amber-200 bg-[#1e1e1e] p-4 text-sm text-white">
                        <button
                            onClick={handleCopy}
                            className="absolute right-4 top-4 rounded p-1.5 text-gray-400 hover:bg-white/10 hover:text-white"
                        >
                            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                        </button>
                        <pre className="overflow-x-auto">
                            <code>{exampleCode}</code>
                        </pre>
                    </div>
                </section>
            </div>
        </div>
    );
}
