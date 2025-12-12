'use client'

import { useCallback, useContext } from "react";

import { I18nContext } from "@/lib/i18n/context";
import type { Locale } from "@/lib/i18n/dictionaries";

export function useI18n() {
  const ctx = useContext(I18nContext);
  const translate = useCallback((key: string, params?: Record<string, string | number>) => {
    let message = ctx.messages[key] ?? key;
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        message = message.replace(`{${k}}`, String(v));
      });
    }
    return message;
  }, [ctx.messages]);
  return { locale: ctx.locale as Locale, t: translate };
}
