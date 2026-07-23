"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, Compass, User, Key } from "lucide-react";
import { useI18n } from "@/lib/i18n/client";

export function MobileBottomNav() {
  const pathname = usePathname();
  const { t } = useI18n();

  const links = [
    {
      href: "/live",
      icon: Home,
      label: t("nav.mobile.arena"),
      accessibleLabel: t("nav.arena"),
    },
    {
      href: "/runs",
      icon: Compass,
      label: t("nav.mobile.runs"),
      accessibleLabel: t("nav.runs"),
    },
    {
      href: "/settings/provider-keys",
      icon: Key,
      label: t("nav.mobile.providerKeys"),
      accessibleLabel: t("settings.nav.providerKeys"),
    },
    {
      href: "/settings/profile",
      icon: User,
      label: t("nav.mobile.profile"),
      accessibleLabel: t("settings.nav.profile"),
    },
  ];

  return (
    <nav
      aria-label={t("nav.mobile.label")}
      className="fixed bottom-0 left-0 right-0 z-50 flex h-[calc(var(--mobile-bottom-nav-height)+env(safe-area-inset-bottom))] items-center justify-around border-t border-border bg-card/80 px-4 pb-[env(safe-area-inset-bottom)] pt-2 shadow-[0_-4px_24px_rgba(0,0,0,0.05)] backdrop-blur-md sm:hidden"
    >
      {links.map((link) => {
        const Icon = link.icon;
        // Strict match for /live to avoid matching everything, loose for others
        const isActive = link.href === "/live" 
            ? pathname === "/live"
            : pathname?.startsWith(link.href);
            
        return (
          <Link
            key={link.href}
            href={link.href}
            aria-label={link.accessibleLabel}
            className={`flex flex-col items-center justify-center gap-1 w-16 transition-colors ${
              isActive ? "text-primary" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <div
              className={`p-1.5 rounded-full transition-transform ${
                isActive ? "bg-primary/10 scale-110" : ""
              }`}
            >
              <Icon className="h-5 w-5" strokeWidth={isActive ? 2.5 : 2} />
            </div>
            <span
              aria-hidden="true"
              className={`max-w-full truncate whitespace-nowrap text-[10px] font-medium tracking-wide ${isActive ? "font-bold" : ""}`}
            >
              {link.label}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}
