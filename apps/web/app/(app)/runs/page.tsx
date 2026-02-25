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

  return (
    <RunsPageClient
      initialQuery={query}
      initialStatus={status}
    />
  );
}
