"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { DebateReplay } from "@/components/debate/DebateReplay";
import { getMe } from "@/lib/auth";

export default function DebateReplayPage({ params }: { params: { debateId: string } }) {
  const router = useRouter();
  const debateId = params.debateId;
  const [checkedAuth, setCheckedAuth] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getMe()
      .then((me) => {
        if (cancelled) return;
        if (!me) {
          router.replace(`/login?next=/debates/${debateId}/replay`);
        } else {
          setCheckedAuth(true);
        }
      })
      .catch(() => {
        if (!cancelled) router.replace(`/login?next=/debates/${debateId}/replay`);
      });
    return () => {
      cancelled = true;
    };
  }, [debateId, router]);

  if (!checkedAuth) {
    return null;
  }

  return (
    <div className="p-4 lg:p-6">
      <DebateReplay debateId={debateId} />
    </div>
  );
}
