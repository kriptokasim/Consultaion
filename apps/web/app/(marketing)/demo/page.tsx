import type { Metadata } from "next"
import DemoClient from "./DemoClient"

export const metadata: Metadata = {
  title: "Interactive Demo",
  description: "Experience side-by-side LLM outputs with synthesized final verdicts using predefined demo scenarios.",
}

export default function DemoPage() {
  return <DemoClient />
}
export const dynamic = "force-dynamic"
