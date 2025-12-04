import { ReactNode } from 'react';
import Image from 'next/image';
import { HERO_BACKGROUNDS } from '@/lib/hero-backgrounds';

interface MarketingHeroProps {
    children?: ReactNode;
    variant?: keyof typeof HERO_BACKGROUNDS;
}

export function MarketingHero({ children, variant = 'parliament' }: MarketingHeroProps) {
    const bg = HERO_BACKGROUNDS[variant];

    return (
        <section className="relative overflow-hidden rounded-3xl border border-amber-100/60 bg-amber-50/50 shadow-2xl shadow-amber-900/5">
            <div className="absolute inset-0">
                <Image
                    src={bg.src}
                    alt={bg.alt}
                    fill
                    priority
                    className="object-cover opacity-20 saturate-50"
                />
                <div className="absolute inset-0 bg-gradient-to-br from-amber-50/90 via-[#fff7eb]/80 to-amber-100/40" />
            </div>

            <div className="relative z-10">
                {children}
            </div>
        </section>
    );
}
