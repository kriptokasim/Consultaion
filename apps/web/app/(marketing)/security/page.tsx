import Link from "next/link";
import { getServerTranslations } from "@/lib/i18n/server";
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Security Policy',
  description: 'Understand the security policies, disclosure guidelines, and infrastructure controls at Consultaion.',
};

export default async function SecurityPage() {
    const { t } = await getServerTranslations();

    return (
        <main className="min-h-screen bg-gradient-to-br from-amber-50 via-[#fff7eb] to-[#f8e6c2] dark:from-stone-900 dark:via-stone-950 dark:to-black px-6 py-16">
            <div className="mx-auto max-w-4xl space-y-8">
                <header className="space-y-4 text-center">
                    <h1 className="text-4xl font-bold text-slate-900 dark:text-white">Security Policy</h1>
                </header>

                <div className="rounded-3xl border border-amber-100/80 bg-white/90 p-8 shadow-lg text-slate-600 dark:text-slate-400 dark:border-slate-800 dark:bg-slate-900 space-y-6">
                    <section className="space-y-2">
                        <h2 className="text-xl font-semibold text-slate-900 dark:text-white">1. Security Architecture</h2>
                        <p>Consultaion employs robust security controls designed to safeguard your account credentials, saved integration keys, and debate telemetry logs.</p>
                    </section>

                    <section className="space-y-2">
                        <h2 className="text-xl font-semibold text-slate-900 dark:text-white">2. Secrets & Environment Separation</h2>
                        <ul className="list-disc pl-5 space-y-1">
                            <li>All production application secrets are strictly separated from development configurations.</li>
                            <li>Critical credentials (JWT secrets, DB credentials, model provider keys) are loaded securely at runtime and rotated periodically.</li>
                            <li>Stripe payment integration signatures are strictly validated on every webhook event.</li>
                        </ul>
                    </section>

                    <section className="space-y-2">
                        <h2 className="text-xl font-semibold text-slate-900 dark:text-white">3. PII Scrubbing Safeguards</h2>
                        <p>We provide automated PII scrubbing to prevent the leakage of sensitive data to upstream AI models. Common identifiers like email addresses, phone numbers, and IP addresses are masked before transmission.</p>
                    </section>

                    <section className="space-y-2">
                        <h2 className="text-xl font-semibold text-slate-900 dark:text-white">4. Vulnerability Disclosure & Reporting</h2>
                        <div className="bg-amber-50 p-4 rounded-lg border border-amber-200/50 text-sm dark:bg-amber-900/20 dark:border-amber-900/30">
                            <p className="dark:text-amber-200"><strong>Responsible Disclosure:</strong> If you discover a vulnerability, please report it to us by emailing <a href="mailto:security@consultaion.com" className="text-amber-700 underline">security@consultaion.com</a>. We request that you do not disclose it publicly until we have had a reasonable timeframe to resolve the issue.</p>
                        </div>
                    </section>

                    <div className="pt-4 border-t border-amber-200/50 text-sm text-amber-900/60 dark:border-slate-800 dark:text-slate-400/60">
                        <p>Last Updated: December 2024</p>
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
