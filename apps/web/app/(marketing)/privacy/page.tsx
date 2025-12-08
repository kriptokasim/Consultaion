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

                <div className="rounded-3xl border border-amber-100/80 bg-white/90 p-8 shadow-lg text-[#5a4a3a] space-y-6">
                    <section className="space-y-2">
                        <h2 className="text-xl font-semibold text-[#3a2a1a]">1. What We Collect</h2>
                        <ul className="list-disc pl-5 space-y-1">
                            <li><strong>Account Information:</strong> Email, display name, and plan details.</li>
                            <li><strong>Debate Content:</strong> Prompts, questions, and generated debate results.</li>
                            <li><strong>Telemetry:</strong> Anonymous usage data (page views, actions) and error logs.</li>
                        </ul>
                    </section>

                    <section className="space-y-2">
                        <h2 className="text-xl font-semibold text-[#3a2a1a]">2. How We Use Your Data</h2>
                        <p>We use your data to:</p>
                        <ul className="list-disc pl-5 space-y-1">
                            <li>Provide the AI debate service and generate results.</li>
                            <li>Manage your account and subscription.</li>
                            <li>Improve platform reliability and user experience.</li>
                            <li>Prevent abuse and ensure security.</li>
                        </ul>
                    </section>

                    <section className="space-y-2">
                        <h2 className="text-xl font-semibold text-[#3a2a1a]">3. Data Retention</h2>
                        <p>We retain data only as long as necessary:</p>
                        <ul className="list-disc pl-5 space-y-1">
                            <li><strong>Debates:</strong> Retained for 365 days, then anonymized or deleted.</li>
                            <li><strong>Telemetry:</strong> Retained for 90 days.</li>
                            <li><strong>Account Info:</strong> Retained until you delete your account.</li>
                        </ul>
                    </section>

                    <section className="space-y-2">
                        <h2 className="text-xl font-semibold text-[#3a2a1a]">4. Your Rights</h2>
                        <p>You have full control over your data:</p>
                        <ul className="list-disc pl-5 space-y-1">
                            <li><strong>Access:</strong> View your debate history at any time.</li>
                            <li><strong>Deletion:</strong> Delete your account and data via Settings.</li>
                            <li><strong>Opt-out:</strong> Disable analytics tracking in Settings.</li>
                        </ul>
                    </section>

                    <section className="space-y-2">
                        <h2 className="text-xl font-semibold text-[#3a2a1a]">5. Third-Party Providers</h2>
                        <p>We use trusted providers to deliver our service:</p>
                        <ul className="list-disc pl-5 space-y-1">
                            <li><strong>AI Models:</strong> OpenAI, Anthropic, Google (for debate generation).</li>
                            <li><strong>Hosting:</strong> Vercel, Render (for infrastructure).</li>
                            <li><strong>Analytics:</strong> PostHog (for usage trends).</li>
                        </ul>
                    </section>

                    <section className="space-y-2">
                        <h2 className="text-xl font-semibold text-[#3a2a1a]">6. Contact</h2>
                        <p>For privacy questions, contact us at <a href="mailto:privacy@consultaion.ai" className="text-amber-700 underline">privacy@consultaion.ai</a>.</p>
                    </section>

                    <div className="pt-4 border-t border-amber-200/50 text-sm text-amber-900/60">
                        <p>Last Updated: December 2024</p>
                        <p>This document is for informational purposes and does not constitute legal advice.</p>
                    </div>
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
