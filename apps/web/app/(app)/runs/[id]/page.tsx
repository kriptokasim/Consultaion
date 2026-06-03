import { notFound } from "next/navigation";
import type { Metadata } from "next";
import RunDetailClient from "./RunDetailClient";
import { API_ORIGIN } from "@/lib/config/runtime";
import { safeMetadataTitle, safeMetadataDescription, containsSensitivePattern } from "@/lib/textSafety";

export async function generateMetadata({ params }: RunDetailProps): Promise<Metadata> {
  const { id } = await params;
  const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || "https://consultaion.com";
  
  try {
    const res = await fetch(`${API_ORIGIN}/debates/${id}`, { cache: "no-store" });
    if (res.ok) {
      const debate = await res.json();
      const isPublic = debate?.is_public === true || debate?.config?.is_public === true;
      const isCompleted = debate?.status === "completed" || debate?.status === "completed_budget";
      
      if (isPublic && isCompleted && debate.prompt) {
        const title = safeMetadataTitle(debate.prompt, true);
        const description = safeMetadataDescription();
        const canonicalUrl = `${baseUrl}/runs/${id}`;

        // Only allow indexing for public, completed, non-sensitive runs
        const isSensitive = containsSensitivePattern(debate.prompt);
        const robots = isSensitive
          ? { index: false, follow: false }
          : { index: true, follow: true };
        
        return {
          title,
          description,
          alternates: { canonical: canonicalUrl },
          robots,
          openGraph: {
            title,
            description,
            type: "website",
            url: canonicalUrl,
          },
          twitter: {
            card: "summary",
            title,
            description,
          },
        };
      }

      // Private or incomplete run — noindex, generic metadata
      return {
        title: "Arena Run | Consultaion",
        robots: { index: false, follow: false },
      };
    }
  } catch (e) {
    // Ignore error, fallback to default
  }

  return {
    title: "Arena Run | Consultaion",
    robots: { index: false, follow: false },
  };
}

export const dynamic = "force-dynamic";

type RunDetailProps = {
  params: Promise<{ id: string }>;
};

export default async function RunDetailPage(props: RunDetailProps) {
  const params = await props.params;
  const { id } = params;
  if (!id) {
    notFound();
  }

  return <RunDetailClient />;
}

