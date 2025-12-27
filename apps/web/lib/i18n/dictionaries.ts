import en from "@/locales/en.json";
import tr from "@/locales/tr.json";

export const LOCALES = ["en", "tr"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "en";

const DICTIONARIES: Record<Locale, Record<string, string>> = {
  tr,
  en,
};

export function getDictionary(locale: Locale): Record<string, string> {
  return DICTIONARIES[locale] ?? DICTIONARIES[DEFAULT_LOCALE];
}

export function isLocale(value: string | undefined): value is Locale {
  return value ? (LOCALES as readonly string[]).includes(value as Locale) : false;
}
