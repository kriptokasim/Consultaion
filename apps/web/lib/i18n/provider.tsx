import type { ReactNode } from "react";
import { cookies } from "next/headers";

import { DEFAULT_LOCALE, getDictionary, isLocale, type Locale } from "@/lib/i18n/dictionaries";
import { I18nClientProvider } from "@/lib/i18n/I18nClientProvider";

export async function resolveLocale(): Promise<Locale> {
  const cookieStore = await cookies();
  const cookieValue = cookieStore?.get?.("consultaion_locale")?.value;
  if (isLocale(cookieValue)) {
    return cookieValue;
  }
  return DEFAULT_LOCALE;
}

export function I18nProvider({ locale, messages, children }: { locale: Locale; messages: Record<string, string>; children: ReactNode }) {
  return <I18nClientProvider locale={locale} messages={messages}>{children}</I18nClientProvider>;
}

export function loadMessages(locale: Locale) {
  return getDictionary(locale);
}
