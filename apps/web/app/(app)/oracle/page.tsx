import { getMe } from "@/lib/auth";
import { redirect } from "next/navigation";
import OracleWorkspace from "@/components/oracle/OracleWorkspace";

export const dynamic = "force-dynamic";

export default async function OraclePage() {
  const profile = await getMe();
  
  if (!profile) {
    redirect("/login?next=/oracle");
  }

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto">
      <OracleWorkspace />
    </div>
  );
}
