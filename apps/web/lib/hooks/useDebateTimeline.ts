import { useEffect, useState } from "react";
import { fetchDebateTimeline, type DebateTimelineEvent } from "../api/debates";

export function useDebateTimeline(debateId: string) {
  const [data, setData] = useState<DebateTimelineEvent[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [statusCode, setStatusCode] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setStatusCode(null);

    fetchDebateTimeline(debateId)
      .then((events) => {
        if (cancelled) return;
        setData(events);
      })
      .catch((err: any) => {
        if (cancelled) return;
        setError(err);
        if (typeof err?.status === "number") {
          setStatusCode(err.status);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [debateId]);

  return { data, loading, error, statusCode };
}
