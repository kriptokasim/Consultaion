"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface PromotionItem {
  id: string;
  title: string;
  body: string;
  cta_label?: string | null;
  cta_url?: string | null;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function PromotionArea({ location }: { location: string }) {
  const [promos, setPromos] = useState<PromotionItem[]>([]);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/promotions?location=${encodeURIComponent(location)}`, { credentials: "include" })
      .then((res) => (res.ok ? res.json() : { items: [] }))
      .then((data) => {
        if (cancelled) return;
        setPromos(Array.isArray(data?.items) ? data.items : []);
      })
      .catch(() => {
        if (!cancelled) setPromos([]);
      });
    return () => {
      cancelled = true;
    };
  }, [location]);

  if (!promos.length) return null;

  return (
    <div className="space-y-3">
      {promos.map((promo) => (
        <Card key={promo.id} className="border-amber-200 bg-gradient-to-br from-white via-[#fff7eb] to-[#fde7c6] p-4 text-[#3a2a1a]">
          <h4 className="font-semibold text-sm">{promo.title}</h4>
          <p className="mt-1 text-xs text-[#5a4a3a]">{promo.body}</p>
          {promo.cta_url && promo.cta_label ? (
            <Button asChild size="sm" className="mt-3 bg-amber-600 text-white hover:bg-amber-700">
              <a href={promo.cta_url}>{promo.cta_label}</a>
            </Button>
          ) : null}
        </Card>
      ))}
    </div>
  );
}

export default PromotionArea;
