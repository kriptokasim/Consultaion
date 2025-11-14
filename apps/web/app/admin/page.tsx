import AdminTabs from "@/components/parliament/AdminTabs";
import { fetchWithAuth, getMe } from "@/lib/auth";
import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

export default async function AdminPage() {
  const profile = await getMe();
  if (!profile || profile.role !== "admin") {
    redirect("/login");
  }

  const [usersRes, logsRes] = await Promise.all([fetchWithAuth("/admin/users"), fetchWithAuth("/admin/logs")]);
  if ([usersRes.status, logsRes.status].some((status) => status === 401 || status === 403)) {
    redirect("/login");
  }
  const [userPayload, logPayload] = await Promise.all([usersRes.json(), logsRes.json()]);
  const users = Array.isArray(userPayload?.items) ? userPayload.items : [];
  const logs = Array.isArray(logPayload?.items) ? logPayload.items : [];

  return (
    <main id="main" className="space-y-6 p-6">
      <header>
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Admin control</p>
        <h1 className="text-3xl font-semibold text-stone-900">Parliament console</h1>
        <p className="text-sm text-stone-600">Audit user activity, quotas, and sharing changes.</p>
      </header>
      <AdminTabs users={users} logs={logs} />
    </main>
  );
}
