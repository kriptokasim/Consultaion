"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useI18n } from "@/lib/i18n/client";
import { PRIMARY_NAV_ITEMS, isNavItemActive } from "@/lib/nav";

export interface PrimaryNavProps {
  /** "inline" renders the desktop horizontal nav; "bottom-bar" the 52px mobile tab bar. */
  variant?: "inline" | "bottom-bar";
  className?: string;
}

/**
 * Canonical New UX navigation (PS04): one registry (lib/nav.ts), rendered
 * as either the desktop inline nav or the mobile bottom tab bar. Both
 * variants set aria-current="page" on the active destination.
 */
export function PrimaryNav({ variant = "inline", className = "" }: PrimaryNavProps) {
  const pathname = usePathname() || "/";
  const { t } = useI18n();

  const variantClass =
    variant === "bottom-bar" ? "new-ux-primary-nav--bottom-bar" : "new-ux-primary-nav--inline";

  return (
    <nav className={`new-ux-primary-nav ${variantClass} ${className}`.trim()} aria-label={t("nav.mobile.label")}>
      {PRIMARY_NAV_ITEMS.map((item) => {
        const active = isNavItemActive(pathname, item);
        return (
          <Link
            key={item.id}
            href={item.href}
            className="new-ux-primary-nav__item"
            aria-current={active ? "page" : undefined}
            data-active={active}
          >
            {t(item.labelKey)}
          </Link>
        );
      })}
    </nav>
  );
}
