"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n/client";
import { BookOpen, Code2, Rocket } from "lucide-react";

export default function DocsPage() {
    const { t } = useI18n();

    return (
        <div className="mx-auto max-w-4xl px-6 py-16">
            <div className="mb-12 text-center">
                <h1 className="text-4xl font-bold text-[#3a2a1a]">{t("docs.title")}</h1>
                <p className="mt-4 text-lg text-[#5a4a3a]">{t("docs.subtitle")}</p>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
                <Link
                    href="/docs/getting-started"
                    className="group relative overflow-hidden rounded-2xl border border-amber-200/70 bg-white p-8 shadow-sm transition hover:-translate-y-1 hover:shadow-md"
                >
                    <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-amber-100 text-amber-700">
                        <Rocket className="h-6 w-6" />
                    </div>
                    <h2 className="text-xl font-semibold text-[#3a2a1a] group-hover:text-amber-700">
                        {t("docs.gettingStarted.title")}
                    </h2>
                    <p className="mt-2 text-[#5a4a3a]">{t("docs.gettingStarted.description")}</p>
                </Link>

                <Link
                    href="/docs/api"
                    className="group relative overflow-hidden rounded-2xl border border-amber-200/70 bg-white p-8 shadow-sm transition hover:-translate-y-1 hover:shadow-md"
                >
                    <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-amber-100 text-amber-700">
                        <Code2 className="h-6 w-6" />
                    </div>
                    <h2 className="text-xl font-semibold text-[#3a2a1a] group-hover:text-amber-700">
                        {t("docs.api.title")}
                    </h2>
                    <p className="mt-2 text-[#5a4a3a]">{t("docs.api.description")}</p>
                </Link>
            </div>
        </div>
    );
}
