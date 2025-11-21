import type { ReactNode } from "react";
import { cookies } from "next/headers";

import { I18nContext } from "@/lib/i18n/context";
import { DEFAULT_LOCALE, getDictionary, isLocale, type Locale } from "@/lib/i18n/dictionaries";

export function resolveLocale(): Locale {
  const cookieStore = cookies() as any;
  const cookieValue = cookieStore?.get?.("consultaion_locale")?.value;
  if (isLocale(cookieValue)) {
    return cookieValue;
  }
  return DEFAULT_LOCALE;
}

export function I18nProvider({ locale, messages, children }: { locale: Locale; messages: Record<string, string>; children: ReactNode }) {
  return <I18nContext.Provider value={{ locale, messages }}>{children}</I18nContext.Provider>;
}

export function loadMessages(locale: Locale) {
  return getDictionary(locale);
}
