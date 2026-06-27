"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, Compass, User, ListPlus } from "lucide-react";

export function MobileBottomNav() {
  const pathname = usePathname();

  const links = [
    { href: "/live", icon: Home, label: "Arena" },
    { href: "/runs", icon: Compass, label: "History" },
    { href: "/models", icon: ListPlus, label: "Models" },
    { href: "/dashboard", icon: User, label: "Profile" },
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 flex items-center justify-around bg-card/80 backdrop-blur-md border-t border-border px-4 pb-[env(safe-area-inset-bottom,16px)] pt-2 sm:hidden shadow-[0_-4px_24px_rgba(0,0,0,0.05)]">
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
            <span className={`text-[10px] font-medium tracking-wide ${isActive ? "font-bold" : ""}`}>
              {link.label}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}
