import { notFound } from "next/navigation";
import ReplayPageClient from "./ReplayPageClient";

export const dynamic = "force-dynamic";

type ReplayPageProps = {
    params: Promise<{ id: string }>;
};

export default async function ReplayPage(props: ReplayPageProps) {
    const params = await props.params;
    const { id } = params;
    if (!id) {
        notFound();
    }

    return <ReplayPageClient id={id} />;
}
