"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n/client";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function GettingStartedPage() {
    const { t } = useI18n();

    return (
        <div className="mx-auto max-w-3xl px-6 py-12">
            <Link
                href="/docs"
                className="mb-8 inline-flex items-center gap-2 text-sm font-medium text-amber-800 hover:text-amber-600"
            >
                <ArrowLeft className="h-4 w-4" />
                {t("nav.goBack")}
            </Link>

            <h1 className="mb-4 text-4xl font-bold text-[#3a2a1a]">{t("docs.gettingStarted.title")}</h1>
            <p className="mb-12 text-lg text-[#5a4a3a]">{t("docs.gettingStarted.description")}</p>

            <div className="space-y-12">
                <section>
                    <div className="mb-4 flex items-center gap-3">
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-amber-100 font-bold text-amber-700">
                            1
                        </div>
                        <h2 className="text-2xl font-semibold text-[#3a2a1a]">{t("docs.gettingStarted.step1.title")}</h2>
                    </div>
                    <div className="pl-11">
                        <p className="text-[#5a4a3a]">{t("docs.gettingStarted.step1.description")}</p>
                    </div>
                </section>

                <section>
                    <div className="mb-4 flex items-center gap-3">
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-amber-100 font-bold text-amber-700">
                            2
                        </div>
                        <h2 className="text-2xl font-semibold text-[#3a2a1a]">{t("docs.gettingStarted.step2.title")}</h2>
                    </div>
                    <div className="pl-11">
                        <p className="mb-4 text-[#5a4a3a]">{t("docs.gettingStarted.step2.description")}</p>
                        <Button variant="outline" asChild>
                            <Link href="/demo">{t("docs.gettingStarted.step2.link")}</Link>
                        </Button>
                    </div>
                </section>

                <section>
                    <div className="mb-4 flex items-center gap-3">
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-amber-100 font-bold text-amber-700">
                            3
                        </div>
                        <h2 className="text-2xl font-semibold text-[#3a2a1a]">{t("docs.gettingStarted.step3.title")}</h2>
                    </div>
                    <div className="pl-11">
                        <p className="mb-4 text-[#5a4a3a]">{t("docs.gettingStarted.step3.description")}</p>
                        <Button variant="amber" asChild>
                            <Link href="/dashboard">{t("docs.gettingStarted.step3.link")}</Link>
                        </Button>
                    </div>
                </section>

                <section>
                    <div className="mb-4 flex items-center gap-3">
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-amber-100 font-bold text-amber-700">
                            4
                        </div>
                        <h2 className="text-2xl font-semibold text-[#3a2a1a]">{t("docs.gettingStarted.step4.title")}</h2>
                    </div>
                    <div className="pl-11">
                        <p className="text-[#5a4a3a]">{t("docs.gettingStarted.step4.description")}</p>
                    </div>
                </section>
            </div>
        </div>
    );
}
