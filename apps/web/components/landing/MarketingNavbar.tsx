"use client"

import Link from "next/link"
import { useRouter, usePathname } from "next/navigation"
import { Brain, Menu, X } from "lucide-react"
import { useEffect, useState } from "react"
import { cn } from "@/lib/utils"
import { useI18n } from "@/lib/i18n/client"
import { trackEvent } from "@/lib/analytics"
import LanguageSwitcher from "@/components/LanguageSwitcher"

export function MarketingNavbar() {
    const router = useRouter()
    const pathname = usePathname()
    const { t } = useI18n()
    const [scrolled, setScrolled] = useState(false)
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

    useEffect(() => {
        const handleScroll = () => {
            setScrolled(window.scrollY > 20)
        }
        window.addEventListener("scroll", handleScroll)
        return () => window.removeEventListener("scroll", handleScroll)
    }, [])

    // Close mobile menu on ESC
    useEffect(() => {
        const handleEscape = (e: KeyboardEvent) => {
            if (e.key === "Escape" && mobileMenuOpen) {
                setMobileMenuOpen(false)
            }
        }
        document.addEventListener("keydown", handleEscape)
        return () => document.removeEventListener("keydown", handleEscape)
    }, [mobileMenuOpen])

    // Prevent body scroll when mobile menu is open
    useEffect(() => {
        if (mobileMenuOpen) {
            document.body.style.overflow = "hidden"
        } else {
            document.body.style.overflow = ""
        }
    }, [mobileMenuOpen])

    const navLinks = [
        { href: "/pricing", label: t("nav.pricing") },
        { href: "/leaderboard", label: t("nav.leaderboard") },
        { href: "/models", label: t("nav.models") },
        { href: "/methodology", label: t("nav.methodology") },
        { href: "/docs", label: t("nav.docs") },
        { href: "/contact", label: t("nav.contact") }
    ]

    return (
        <>
            <nav
                className={cn(
                    "fixed top-0 left-0 right-0 z-50 transition-all duration-300",
                    scrolled
                        ? "bg-amber-50/95 backdrop-blur-lg shadow-md py-3 dark:bg-slate-900/95"
                        : "bg-amber-50/80 backdrop-blur-sm py-4 dark:bg-transparent"
                )}
            >
                <div className="container mx-auto px-6">
                    <div className="flex items-center justify-between">
                        {/* Logo */}
                        <Link href="/" className="flex items-center gap-2">
                            <Brain className="h-7 w-7 text-amber-700 dark:text-amber-400" />
                            <span className="text-xl font-bold text-amber-900 dark:text-white drop-shadow-md [text-shadow:0_1px_2px_rgba(0,0,0,0.1)]">Consultaion</span>
                        </Link>

                        {/* Desktop Navigation */}
                        <div className="hidden md:flex items-center gap-6">
                            {navLinks.map((link) => (
                                <Link
                                    key={link.href}
                                    href={link.href}
                                    className={cn(
                                        "text-sm font-semibold transition-colors",
                                        pathname === link.href
                                            ? "text-amber-900 dark:text-amber-400 drop-shadow-md [text-shadow:0_1px_2px_rgba(0,0,0,0.1)]"
                                            : "text-amber-800 hover:text-amber-950 dark:text-white dark:hover:text-amber-400 drop-shadow-md [text-shadow:0_1px_2px_rgba(0,0,0,0.1)]"
                                    )}
                                >
                                    {link.label}
                                </Link>
                            ))}

                            <LanguageSwitcher />

                            <Link
                                href="/login?next=/dashboard"
                                className="rounded-lg bg-gradient-to-r from-amber-500 to-amber-600 px-5 py-2 text-sm font-semibold text-white shadow-md transition hover:-translate-y-[1px] hover:shadow-lg"
                            >
                                {t("nav.cta")}
                            </Link>
                        </div>

                        {/* Mobile Menu Button */}
                        <button
                            onClick={() => {
                                setMobileMenuOpen(true);
                                trackEvent("mobile_nav_opened");
                            }}
                            className="md:hidden rounded-lg border border-amber-200 bg-white/80 p-2 text-amber-900 hover:bg-amber-50 dark:border-amber-700 dark:bg-slate-800/80 dark:text-white dark:hover:bg-slate-700 transition"
                            aria-label={t("nav.mobile.open")}
                        >
                            <Menu className="h-6 w-6" />
                        </button>
                    </div>
                </div>
            </nav>

            {/* Mobile Menu Overlay */}
            {mobileMenuOpen && (
                <>
                    {/* Backdrop */}
                    <div
                        className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm"
                        onClick={() => setMobileMenuOpen(false)}
                    />

                    {/* Drawer */}
                    <div className="fixed top-0 right-0 bottom-0 z-50 w-80 bg-gradient-to-br from-[#fff7eb] to-amber-50 dark:from-slate-900 dark:to-slate-800 shadow-2xl overflow-y-auto">
                        <div className="p-6 space-y-6">
                            {/* Close Button */}
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <Brain className="h-6 w-6 text-amber-700 dark:text-amber-400" />
                                    <span className="text-lg font-bold text-amber-900 dark:text-white">Consultaion</span>
                                </div>
                                <button
                                    onClick={() => setMobileMenuOpen(false)}
                                    className="rounded-lg p-2 text-amber-900 hover:bg-amber-100 dark:text-white dark:hover:bg-amber-900/30 transition"
                                    aria-label={t("nav.mobile.close")}
                                >
                                    <X className="h-6 w-6" />
                                </button>
                            </div>

                            {/* Navigation Links */}
                            <nav className="space-y-2">
                                {navLinks.map((link) => (
                                    <Link
                                        key={link.href}
                                        href={link.href}
                                        onClick={() => {
                                            setMobileMenuOpen(false);
                                            trackEvent("mobile_nav_link_clicked", { target: link.label.toLowerCase() });
                                        }}
                                        className={cn(
                                            "block rounded-lg px-4 py-3 text-lg font-semibold transition-colors",
                                            pathname === link.href
                                                ? "bg-amber-100 text-amber-900 dark:bg-amber-900/50 dark:text-amber-200"
                                                : "text-amber-800 hover:bg-amber-50 dark:text-white dark:hover:bg-amber-900/30"
                                        )}
                                    >
                                        {link.label}
                                    </Link>
                                ))}
                            </nav>

                            {/* Language Switcher */}
                            <div className="pt-4 border-t border-amber-200 dark:border-slate-700">
                                <LanguageSwitcher />
                            </div>

                            {/* CTA Button */}
                            <Link
                                href="/login?next=/dashboard"
                                onClick={() => setMobileMenuOpen(false)}
                                className="block w-full rounded-lg bg-gradient-to-r from-amber-500 to-amber-600 px-5 py-3 text-center text-sm font-semibold text-white shadow-md transition hover:shadow-lg"
                            >
                                {t("nav.cta")}
                            </Link>
                        </div>
                    </div>
                </>
            )}
        </>
    )
}
