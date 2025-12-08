import Link from "next/link";
import { getServerTranslations } from "@/lib/i18n/server";

export default async function ContactPage() {
    const { t } = await getServerTranslations();

    return (
        <main className="min-h-screen bg-gradient-to-br from-amber-50 via-[#fff7eb] to-[#f8e6c2] px-6 py-16">
            <div className="mx-auto max-w-4xl space-y-8">
                <header className="space-y-4 text-center">
                    <h1 className="text-4xl font-bold text-[#3a2a1a]">{t("pages.contact.title")}</h1>
                    <p className="text-lg text-[#5a4a3a]">{t("pages.contact.subtitle")}</p>
                </header>

                <div className="rounded-3xl border border-amber-100/80 bg-white/90 p-8 shadow-lg">
                    {/* TODO: Replace with actual contact form or information */}
                    <div className="space-y-6">
                        <div>
                            <h2 className="text-xl font-semibold text-[#3a2a1a] mb-4">
                                {t("pages.contact.getInTouch")}
                            </h2>
                            <p className="text-[#5a4a3a]">
                                {t("pages.contact.placeholder")}
                            </p>
                        </div>

                        <div className="border-t border-amber-100 pt-6">
                            <h3 className="text-lg font-semibold text-[#3a2a1a] mb-3">
                                {t("pages.contact.channels")}
                            </h3>
                            <ul className="space-y-2 text-[#5a4a3a]">
                                <li>
                                    <strong>Email:</strong> contact@consultaion.ai
                                </li>
                                <li>
                                    <strong>Support:</strong> support@consultaion.ai
                                </li>
                            </ul>
                        </div>
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
