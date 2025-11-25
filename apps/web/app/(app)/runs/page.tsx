import { getServerTranslations } from "@/lib/i18n/server";
import RunsPageClient from "./RunsPageClient";

export const dynamic = "force-dynamic";

type RunsPageProps = {
  searchParams: Promise<{ q?: string; status?: string }>;
};

export default async function RunsPage({ searchParams }: RunsPageProps) {
  const params = await searchParams;
  const query = params?.q ?? "";
  const status = params?.status ?? "";
  const { t } = await getServerTranslations();

  // We need to pass the translations object, but t returns a string.
  // getServerTranslations returns { t, i18n }.
  // We can't easily pass the t function to client component.
  // We should extract the keys we need or pass a dictionary.
  // For now, let's construct a dictionary of used keys.
  // This is a bit manual but works for now.
  const translationKeys = [
    "runs.hero.kicker",
    "runs.hero.title",
    "runs.hero.badge",
    "runs.hero.description",
    "runs.status.kicker",
    "runs.status.total",
    "runs.status.inProgress",
    "runs.status.note",
    "runs.list.kicker",
    "runs.list.title",
    "runs.list.caption",
  ];

  const translations: Record<string, string> = {};
  translationKeys.forEach(key => {
    translations[key] = t(key);
  });

  return (
    <RunsPageClient
      initialQuery={query}
      initialStatus={status}
      translations={translations}
    />
  );
}
