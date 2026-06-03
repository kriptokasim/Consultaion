import type { Metadata } from "next"
import ApiClient from "./ApiClient"

export const metadata: Metadata = {
  title: "API Reference",
  description: "Learn how to programmatically simulate and compare model outputs using our API.",
}

export default function ApiDocsPage() {
  return <ApiClient />
}
