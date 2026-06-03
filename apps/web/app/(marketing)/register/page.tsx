import type { Metadata } from "next"
import RegisterClient from "./RegisterClient"

export const metadata: Metadata = {
  title: "Create an Account",
  description: "Sign up for Consultaion to start comparing and analyzing LLM output debates side-by-side.",
}

export default function RegisterPage() {
  return <RegisterClient />
}
