import { Button } from "@/components/ui/button";
import { Scale } from "lucide-react";

export interface HeroProps {
  title?: string;
  subtitle?: string;
  onStart?: () => void;
}

export default function Hero({ 
  title = "AI Parliament", 
  subtitle = "Democratic AI decision-making via multi-agent debate, judicial scoring, and voting.",
  onStart 
}: HeroProps) {
  return (
    <section 
      className="relative overflow-hidden rounded-2xl border bg-gradient-to-br from-[--muted] to-[--parl-blue] p-8 md:p-16 [--parl-blue:#0B1D3A] [--parl-gold:#D4AF37] [--muted:#101827]"
      aria-labelledby="hero-title"
    >
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(212,175,55,0.1),transparent_50%)]" aria-hidden="true" />
      
      <div className="relative z-10 max-w-4xl mx-auto text-center space-y-6">
        <div className="inline-flex items-center gap-2 px-4 py-2 bg-[--parl-gold]/10 rounded-full border border-[--parl-gold]/30">
          <Scale className="w-4 h-4 text-[--parl-gold]" aria-hidden="true" />
          <span className="text-sm font-medium text-[--parl-gold]">Democracy Meets Artificial Intelligence</span>
        </div>

        <h1 
          id="hero-title"
          className="text-4xl md:text-6xl font-bold tracking-tight text-[--parl-gold]"
        >
          {title}
        </h1>

        <p className="mt-4 max-w-2xl mx-auto text-base md:text-lg text-white/80 leading-relaxed">
          {subtitle}
        </p>

        {onStart && (
          <div className="mt-8">
            <Button 
              onClick={onStart}
              size="lg"
              className="bg-[--parl-gold] text-black hover:bg-[--parl-gold]/90 font-semibold px-8 py-6 text-lg shadow-lg hover:shadow-xl transition-all focus-visible:ring-2 focus-visible:ring-[--parl-gold] focus-visible:ring-offset-2"
            >
              Start Session
            </Button>
          </div>
        )}
      </div>
    </section>
  );
}
