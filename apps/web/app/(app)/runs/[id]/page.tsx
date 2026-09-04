import { notFound } from "next/navigation";
import type { Metadata } from "next";
import RunDetailClient from "./RunDetailClient";
import { API_ORIGIN } from "@/lib/config/runtime";
import { safeMetadataTitle, safeMetadataDescription, containsSensitivePattern } from "@/lib/textSafety";
import { isSuccessfulRunStatus } from "@/lib/runStatus";

export async function generateMetadata({ params }: RunDetailProps): Promise<Metadata> {
  const { id } = await params;
  const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || "https://consultaion.com";
  try {
    const res = await fetch(`${API_ORIGIN}/debates/${id}`, { cache: "no-store" });
    if (res.ok) {
      const debate = await res.json();
      const isPublic = debate?.is_public === true || debate?.config?.is_public === true;
      const isCompleted = isSuccessfulRunStatus(debate?.status);
      if (isPublic && isCompleted && debate.prompt) {
        const title = safeMetadataTitle(debate.prompt, true);
        const description = safeMetadataDescription();
        const canonicalUrl = `${baseUrl}/runs/${id}`;
        const isSensitive = containsSensitivePattern(debate.prompt);
        const robots = isSensitive ? { index: false, follow: false } : { index: true, follow: true };
        const meta = debate?.final_meta || {};
        const quality = debate?.quality_meta || meta?.quality_meta || {};
        const divergenceValue = typeof meta?.divergence_score === "number" ? Math.round(meta.divergence_score * 100) : null;
        const confidenceValue = typeof meta?.confidence === "number" ? Math.round(meta.confidence * 100) : null;
        const winner = typeof meta?.winner === "string" ? meta.winner : typeof meta?.champion === "string" ? meta.champion : null;
        const verified = quality?.verification_status === "verified" && quality?.verification_error !== true;
        const ogParams = new URLSearchParams({ title, models: String(meta?.models?.length || 4) });
        if (divergenceValue != null) ogParams.set("divergence", String(divergenceValue));
        if (confidenceValue != null) ogParams.set("confidence", String(confidenceValue));
        if (winner) ogParams.set("winner", winner);
        if (verified) ogParams.set("verified", "1");
        const ogUrl = `${baseUrl}/api/og?${ogParams.toString()}`;
        return {
          title,
          description,
          alternates: { canonical: canonicalUrl },
          robots,
          openGraph: { title, description, type: "website", url: canonicalUrl, images: [{ url: ogUrl, width: 1200, height: 630, alt: title }] },
          twitter: { card: "summary_large_image", title, description, images: [ogUrl] },
        };
      }
      return { title: "Arena Run | Consultaion", robots: { index: false, follow: false } };
    }
  } catch {
    // Metadata generation must never block a public run page.
  }
  return { title: "Arena Run | Consultaion", robots: { index: false, follow: false } };
}

export const dynamic = "force-dynamic";

type RunDetailProps = { params: Promise<{ id: string }> };

export default async function RunDetailPage(props: RunDetailProps) {
  const params = await props.params;
  const { id } = params;
  if (!id) notFound();
  return <RunDetailClient />;
}
