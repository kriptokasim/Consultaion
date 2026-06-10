import HomeContent from "@/components/landing/HomeContent";
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Consultaion — One Question, Multiple AI Perspectives, One Decision Report',
  description: 'Submit one question and get structured comparison across multiple AI models. Consultaion surfaces where models agree or disagree and delivers a clear decision report with verdict, risks, and next actions.',
};


export default function LandingPage() {
  return <HomeContent />;
}
