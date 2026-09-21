/**
 * Canonical New UX navigation registry (PS04). SCREEN-SPEC's four mobile
 * primary destinations: Runs, Ask, Panel, You. This does not replace the
 * legacy nav arrays in dashboard-shell.tsx / MobileBottomNav.tsx /
 * AdminShell.tsx / MarketingNavbar.tsx yet — those still drive the
 * pre-New-UX surfaces and are only removed after their consumers migrate
 * (AUDIT-RESOLUTION deletion rule). New-ux surfaces (the unified workspace,
 * and anything built on it) should consume PRIMARY_NAV_ITEMS from here.
 *
 * "Panel" reuses the same tab slot the legacy mobile nav gave to
 * provider-key management (Keys) — the closest existing surface to
 * "the models/providers in your panel" — rather than inventing a new page.
 */

export interface NavItem {
  id: string;
  labelKey: string;
  href: string;
}

export const PRIMARY_NAV_ITEMS: readonly NavItem[] = [
  { id: "runs", labelKey: "nav.runs", href: "/runs" },
  { id: "ask", labelKey: "nav.ask", href: "/new" },
  { id: "panel", labelKey: "nav.panel", href: "/settings/provider-keys" },
  { id: "you", labelKey: "nav.you", href: "/settings" },
];

/**
 * True when `item` is the best (longest-prefix) match for `pathname` among
 * `items`, so two nested routes (e.g. /settings and /settings/provider-keys)
 * never both report as active for the same URL.
 */
export function isNavItemActive(
  pathname: string,
  item: NavItem,
  items: readonly NavItem[] = PRIMARY_NAV_ITEMS,
): boolean {
  if (pathname === item.href) return true;
  if (!pathname.startsWith(`${item.href}/`)) return false;
  return !items.some(
    (other) =>
      other.href !== item.href &&
      other.href.length > item.href.length &&
      (pathname === other.href || pathname.startsWith(`${other.href}/`)),
  );
}
