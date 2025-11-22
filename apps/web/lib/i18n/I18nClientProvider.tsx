'use client'

import type { ReactNode } from "react";

import { I18nContext } from "@/lib/i18n/context";
import type { Locale } from "@/lib/i18n/dictionaries";

export function I18nClientProvider({ locale, messages, children }: { locale: Locale; messages: Record<string, string>; children: ReactNode }) {
  return <I18nContext.Provider value={{ locale, messages }}>{children}</I18nContext.Provider>;
}
