'use client'

import { useCallback, useContext } from "react";

import { I18nContext } from "@/lib/i18n/context";
import type { Locale } from "@/lib/i18n/dictionaries";

export function useI18n() {
  const ctx = useContext(I18nContext);
  const translate = useCallback((key: string) => ctx.messages[key] ?? key, [ctx.messages]);
  return { locale: ctx.locale as Locale, t: translate };
}
