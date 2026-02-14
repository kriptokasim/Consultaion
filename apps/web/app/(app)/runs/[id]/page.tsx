import { notFound } from "next/navigation";
import RunDetailClient from "./RunDetailClient";

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

