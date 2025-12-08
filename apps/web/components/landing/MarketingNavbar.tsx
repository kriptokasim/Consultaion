"use client"

import Link from "next/link"
import { useRouter, usePathname } from "next/navigation"
import { Brain, Menu, X } from "lucide-react"
import { useEffect, useState } from "react"
import { cn } from "@/lib/utils"
import { useI18n } from "@/lib/i18n/client"
import LanguageSwitcher from "@/components/LanguageSwitcher"

export function MarketingNavbar() {
    const router = useRouter()
    const pathname = usePathname()
    const { t } = useI18n()
    const [scrolled, setScrolled] = useState(false)
    const [user, setUser] = useState<{ email: string } | null>(null)
    const [loading, setLoading] = useState(true)
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

    // Detect scroll for sticky behavior
    useEffect(() => {
        const handleScroll = () => {
            setScrolled(window.scrollY > 20)
        }
        window.addEventListener("scroll", handleScroll)
        return () => window.removeEventListener("scroll", handleScroll)
    }, [])

    // Check user auth status
    useEffect(() => {
        let cancelled = false
        const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
        fetch(`${apiBase}/me`, { credentials: "include", cache: "no-store" })
            .then((res) => (res.ok ? res.json() : null))
            .then((data) => {
                if (!cancelled) setUser(data)
            })
            .catch(() => {
                if (!cancelled) setUser(null)
            })
            .finally(() => {
                if (!cancelled) setLoading(false)
            })
        return () => {
            cancelled = true
        }
    }, [])

    // Handle ESC key for mobile menu
    useEffect(() => {
        const handleEsc = (e: KeyboardEvent) => {
            if (e.key === "Escape" && mobileMenuOpen) {
                setMobileMenuOpen(false)
            }
        }
        window.addEventListener("keydown", handleEsc)
        return () => window.removeEventListener("keydown", handleEsc)
    }, [mobileMenuOpen])

    // Prevent body scroll when menu is open
    useEffect(() => {
        if (mobileMenuOpen) {
            document.body.style.overflow = "hidden"
        } else {
            document.body.style.overflow = ""
        }
        return () => {
            document.body.style.overflow = ""
        }
    }, [mobileMenuOpen])

    const marketingLinks = [
        { href: "/pricing", label: t("nav.pricing") },
        { href: "/leaderboard", label: t("nav.leaderboard") },
        { href: "/models", label: t("nav.models") },
        { href: "/methodology", label: t("nav.methodology") },
        { href: "/contact", label: t("footer.contact") },
    ]

    const handleStartDebate = () => {
        if (loading) return
        if (user) {
            router.push("/dashboard")
        } else {
            router.push("/login?next=/dashboard")
        }
    }

    const handleMobileLinkClick = () => {
        setMobileMenuOpen(false)
    }

    return (
        <>
            <nav
                className={cn(
                    "fixed top-0 left-0 right-0 z-50 transition-all duration-300",
                    scrolled
                        ? "bg-[#FFF7EB]/95 backdrop-blur-md shadow-sm py-3"
                        : "bg-transparent py-4"
                )}
            >
                <div className="mx-auto flex max-w-6xl items-center justify-between px-6">
                    {/* Logo */}
                    <Link
                        href="/"
                        className="flex items-center gap-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2"
                    >
                        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-500 to-amber-600 text-white shadow-lg shadow-amber-200/50 transition-transform hover:scale-105">
                            <Brain className="h-5 w-5" />
                        </div>
                        <span className="text-xl font-display font-bold text-[#3a2a1a]">
                            Consultaion
                        </span>
                    </Link>

                    {/* Desktop Navigation */}
                    <div className="hidden md:flex items-center gap-6">
                        {marketingLinks.map((item) => (
                            <Link
                                key={item.href}
                                href={item.href}
                                className={cn(
                                    "text-sm font-semibold transition-colors hover:text-amber-700",
                                    pathname === item.href
                                        ? "text-amber-700"
                                        : "text-[#6b5844]"
                                )}
                            >
                                {item.label}
                            </Link>
                        ))}
                    </div>

                    {/* Right side: Hamburger (mobile) + Language + CTA (desktop) */}
                    <div className="flex items-center gap-4">
                        {/* Hamburger Button - Mobile Only */}
                        <button
                            onClick={() => setMobileMenuOpen(true)}
                            className="md:hidden rounded-lg p-2 text-amber-900 transition hover:bg-amber-100"
                            aria-label={t("nav.mobile.open")}
                        >
                            <Menu className="h-6 w-6" />
                        </button>

                        {/* Desktop: Language + CTA */}
                        <div className="hidden md:flex items-center gap-4">
                            <LanguageSwitcher />

                            {user ? (
                                <Link
                                    href="/dashboard"
                                    className="rounded-lg border border-amber-200 bg-white px-4 py-2 text-sm font-semibold text-amber-900 shadow-sm transition hover:-translate-y-[1px] hover:shadow-md"
                                >
                                    {t("landing.nav.dashboard")}
                                </Link>
                            ) : (
                                <button
                                    onClick={handleStartDebate}
                                    disabled={loading}
                                    className="rounded-lg bg-gradient-to-r from-amber-500 to-amber-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:-translate-y-[1px] hover:shadow-md disabled:opacity-50"
                                >
                                    {t("landing.hero.primaryCta")}
                                </button>
                            )}
                        </div>
                    </div>
                </div>
            </nav>

            {/* Mobile Menu */}
            {mobileMenuOpen && (
                <>
                    {/* Backdrop */}
                    <div
                        className="fixed inset-0 z-[60] bg-black/50 backdrop-blur-sm"
                        onClick={() => setMobileMenuOpen(false)}
                        aria-hidden="true"
                    />

                    {/* Drawer */}
                    <div className="fixed top-0 right-0 bottom-0 z-[70] w-80 bg-gradient-to-br from-[#FFF7EB] to-[#FFF3DE] shadow-2xl">
                        <div className="flex h-full flex-col p-6">
                            {/* Header */}
                            <div className="flex items-center justify-between mb-8">
                                <span className="text-lg font-display font-bold text-[#3a2a1a]">
                                    Menu
                                </span>
                                <button
                                    onClick={() => setMobileMenuOpen(false)}
                                    className="rounded-lg p-2 text-amber-900 transition hover:bg-amber-100"
                                    aria-label={t("nav.mobile.close")}
                                >
                                    <X className="h-6 w-6" />
                                </button>
                            </div>

                            {/* Nav Links */}
                            <nav className="flex-1 space-y-2">
                                {marketingLinks.map((item) => (
                                    <Link
                                        key={item.href}
                                        href={item.href}
                                        onClick={handleMobileLinkClick}
                                        className={cn(
                                            "block rounded-lg px-4 py-3 text-base font-semibold transition-colors",
                                            pathname === item.href
                                                ? "bg-amber-100 text-amber-900"
                                                : "text-[#6b5844] hover:bg-amber-50"
                                        )}
                                    >
                                        {item.label}
                                    </Link>
                                ))}
                            </nav>

                            {/* Language Toggle */}
                            <div className="mb-4">
                                <LanguageSwitcher />
                            </div>

                            {/* CTA */}
                            <div className="border-t border-amber-200 pt-4">
                                {user ? (
                                    <Link
                                        href="/dashboard"
                                        onClick={handleMobileLinkClick}
                                        className="block w-full rounded-lg border border-amber-200 bg-white px-4 py-3 text-center text-sm font-semibold text-amber-900 shadow-sm transition hover:shadow-md"
                                    >
                                        {t("landing.nav.dashboard")}
                                    </Link>
                                ) : (
                                    <button
                                        onClick={() => {
                                            handleStartDebate()
                                            setMobileMenuOpen(false)
                                        }}
                                        disabled={loading}
                                        className="w-full rounded-lg bg-gradient-to-r from-amber-500 to-amber-600 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:shadow-md disabled:opacity-50"
                                    >
                                        {t("landing.hero.primaryCta")}
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                </>
            )}
        </>
    )
}

