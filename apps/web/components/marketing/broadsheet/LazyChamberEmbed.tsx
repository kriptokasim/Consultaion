"use client";

import { useEffect, useRef, useState } from "react";
import { useI18n } from "@/lib/i18n/client";

/**
 * Lazily mounts the existing chamber embed (apps/web/public/embeds/consultaion-chamber.html)
 * once it scrolls near the viewport. The embed itself already owns its 2D
 * fallback and WebGL failure handling (D3/D4) — this wrapper only decides
 * *when* to mount the iframe, it never reimplements chamber rendering.
 */
export function LazyChamberEmbed({ className = "" }: { className?: string }) {
  const { t } = useI18n();
  const ref = useRef<HTMLDivElement | null>(null);
  const [shouldMount, setShouldMount] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (node.getBoundingClientRect().top < window.innerHeight * 1.2) {
      setShouldMount(true);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShouldMount(true);
          observer.disconnect();
        }
      },
      { rootMargin: "200px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={ref} className={`new-ux-marketing__hero-figure ${className}`.trim()}>
      {shouldMount ? (
        <iframe
          title={t("marketing.chamber.title")}
          src="/embeds/consultaion-chamber.html"
          loading="lazy"
          aria-label={t("marketing.chamber.title")}
        />
      ) : null}
    </div>
  );
}
