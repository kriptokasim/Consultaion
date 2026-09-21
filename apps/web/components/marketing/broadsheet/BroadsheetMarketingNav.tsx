"use client";

import { Link } from "next-view-transitions";
import { usePathname } from "next/navigation";
import { Menu, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useI18n } from "@/lib/i18n/client";
import { trackEvent } from "@/lib/analytics";
import LanguageSwitcher from "@/components/LanguageSwitcher";

/**
 * Broadsheet-styled replacement for MarketingNavbar.tsx, reusing the exact
 * same links and the same focus/ESC/scroll-lock a11y behavior — only the
 * visual language changes (paper surface, serif, cyan spot instead of amber
 * gradients), so the whole marketing surface reads as one system.
 * MarketingNavbar.tsx itself is left in place; nothing else still imports it
 * once app/(marketing)/layout.tsx switches over.
 */
export function BroadsheetMarketingNav() {
  const pathname = usePathname();
  const { t } = useI18n();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const prevOpen = useRef(mobileMenuOpen);

  useEffect(() => {
    if (prevOpen.current && !mobileMenuOpen) {
      menuButtonRef.current?.focus();
    }
    prevOpen.current = mobileMenuOpen;
  }, [mobileMenuOpen]);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && mobileMenuOpen) setMobileMenuOpen(false);
    };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [mobileMenuOpen]);

  useEffect(() => {
    document.body.style.overflow = mobileMenuOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [mobileMenuOpen]);

  const navLinks = [
    { href: "/pricing", label: t("nav.pricing") },
    { href: "/models", label: t("nav.models") },
    { href: "/methodology", label: t("nav.methodology") },
    { href: "/docs", label: t("nav.docs") },
    { href: "/contact", label: t("nav.contact") },
  ];

  return (
    <>
      <nav className="new-ux-marketing__navbar">
        <div className="new-ux-marketing__shell new-ux-marketing__navbar-inner">
          <Link href="/" className="new-ux-marketing__brand">
            Consultaion
          </Link>

          <div className="new-ux-marketing__navbar-links">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                aria-current={pathname === link.href ? "page" : undefined}
                className="new-ux-marketing__navbar-link"
              >
                {link.label}
              </Link>
            ))}
            <LanguageSwitcher />
            <Link href="/login?next=/new" className="new-ux-marketing__primary">
              {t("nav.cta")}
            </Link>
          </div>

          <button
            ref={menuButtonRef}
            type="button"
            onClick={() => {
              setMobileMenuOpen(true);
              trackEvent("mobile_nav_opened");
            }}
            className="new-ux-marketing__navbar-toggle"
            aria-label={t("nav.mobile.open")}
          >
            <Menu className="h-5 w-5" />
          </button>
        </div>
      </nav>

      {mobileMenuOpen && (
        <>
          <button
            type="button"
            aria-label={t("nav.mobile.close")}
            className="new-ux-marketing__navbar-backdrop"
            onClick={() => setMobileMenuOpen(false)}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-label={t("nav.mobile.label")}
            className="new-ux-marketing__navbar-drawer"
          >
            <div className="new-ux-marketing__navbar-drawer-head">
              <span className="new-ux-marketing__brand">Consultaion</span>
              <button
                type="button"
                onClick={() => setMobileMenuOpen(false)}
                aria-label={t("nav.mobile.close")}
                className="new-ux-marketing__navbar-toggle"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <nav aria-label={t("nav.mobile.label")} className="new-ux-marketing__navbar-drawer-links">
              {navLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => {
                    setMobileMenuOpen(false);
                    trackEvent("mobile_nav_link_clicked", { target: link.label.toLowerCase() });
                  }}
                  aria-current={pathname === link.href ? "page" : undefined}
                  className="new-ux-marketing__navbar-drawer-link"
                >
                  {link.label}
                </Link>
              ))}
            </nav>
            <div className="new-ux-marketing__navbar-drawer-foot">
              <LanguageSwitcher />
              <Link
                href="/login?next=/new"
                onClick={() => setMobileMenuOpen(false)}
                className="new-ux-marketing__primary"
              >
                {t("nav.cta")}
              </Link>
            </div>
          </div>
        </>
      )}
    </>
  );
}
