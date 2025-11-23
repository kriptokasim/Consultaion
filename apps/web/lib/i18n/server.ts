import { loadMessages, resolveLocale } from "@/lib/i18n/provider"

type Translator = (key: string) => string

export async function getServerTranslations(): Promise<{ locale: string; t: Translator }> {
  const locale = await resolveLocale()
  const messages = loadMessages(locale)
  const t: Translator = (key) => messages[key] ?? key
  return { locale, t }
}
