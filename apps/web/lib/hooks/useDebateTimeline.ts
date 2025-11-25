import { useQuery } from "@tanstack/react-query";
import { fetchDebateTimeline } from "../api/debates";

export function useDebateTimeline(debateId: string) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["debate-timeline", debateId],
    queryFn: () => fetchDebateTimeline(debateId),
    enabled: !!debateId,
  });

  return { data, loading: isLoading, error };
}
