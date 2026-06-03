import { notFound } from "next/navigation";
import type { Metadata } from "next";
import RunDetailClient from "./RunDetailClient";
import { API_ORIGIN } from "@/lib/config/runtime";

export async function generateMetadata({ params }: RunDetailProps): Promise<Metadata> {
  const { id } = await params;
  
  try {
    const res = await fetch(`${API_ORIGIN}/debates/${id}`, { cache: "no-store" });
    if (res.ok) {
      const debate = await res.json();
      const isPublic = debate?.config?.is_public === true;
      
      if (isPublic && debate.prompt) {
        const shortPrompt = debate.prompt.length > 60 ? debate.prompt.substring(0, 57) + "..." : debate.prompt;
        const title = `Arena Run: ${shortPrompt} | Consultaion`;
        const description = "Compare multiple AI model responses and read the synthesized answer.";
        
        return {
          title,
          description,
          openGraph: {
            title,
            description,
            type: "website",
          },
          twitter: {
            card: "summary",
            title,
            description,
          }
        };
      }
    }
  } catch (e) {
    // Ignore error, fallback to default
  }

  return {
    title: "Arena Run | Consultaion"
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

