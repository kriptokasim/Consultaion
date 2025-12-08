import Link from "next/link";
import { getServerTranslations } from "@/lib/i18n/server";

export default async function PrivacyPage() {
    const { t } = await getServerTranslations();

    return (
        <main className="min-h-screen bg-gradient-to-br from-amber-50 via-[#fff7eb] to-[#f8e6c2] px-6 py-16">
            <div className="mx-auto max-w-4xl space-y-8">
                <header className="space-y-4 text-center">
                    <h1 className="text-4xl font-bold text-[#3a2a1a]">{t("pages.privacy.title")}</h1>
                </header>

                <div className="rounded-3xl border border-amber-100/80 bg-white/90 p-8 shadow-lg">
                    {/* TODO: Replace with actual Privacy Policy content */}
                    <p className="text-center text-lg text-[#5a4a3a]">{t("pages.privacy.placeholder")}</p>
                </div>

                <div className="text-center">
                    <Link
                        href="/"
                        className="inline-flex items-center text-sm font-semibold text-amber-700 underline-offset-4 hover:underline"
                    >
                        ← {t("pages.placeholder.backHome")}
                    </Link>
                </div>
            </div>
        </main>
    );
}
