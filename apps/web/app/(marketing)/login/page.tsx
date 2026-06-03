import type { Metadata } from "next"
import LoginClient from "./LoginClient"

export const metadata: Metadata = {
  title: "Sign In",
  description: "Sign in to Consultaion to compare LLM outputs side-by-side and view AI debate metrics.",
}

export default function LoginPage() {
  return <LoginClient />
}
