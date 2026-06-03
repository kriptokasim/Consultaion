import HomeContent from "@/components/landing/HomeContent";
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Consultaion — Ask Once, Get Answers from Every Top AI',
  description: 'Submit one question and get simultaneous answers from GPT-4o, Claude, Gemini, and DeepSeek. Compare AI perspectives side-by-side and get a synthesized final verdict.',
};

export const dynamic = "force-dynamic";

export default function LandingPage() {
  return <HomeContent />;
}
