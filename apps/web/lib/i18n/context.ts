'use client'

import { createContext } from "react";
import type { Locale } from "@/lib/i18n/dictionaries";

export type Messages = Record<string, string>;

export const I18nContext = createContext<{ locale: Locale; messages: Messages }>({
  locale: "tr",
  messages: {},
});
