import { getMe } from "@/lib/auth";
import { redirect } from "next/navigation";
import RedTeamWorkspace from "@/components/redteam/RedTeamWorkspace";

export const dynamic = "force-dynamic";

export default async function RedTeamPage() {
  const profile = await getMe();
  
  if (!profile) {
    redirect("/login?next=/redteam");
  }

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto">
      <RedTeamWorkspace />
    </div>
  );
}
