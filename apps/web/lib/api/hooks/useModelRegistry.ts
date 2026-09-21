import { useQuery } from "@tanstack/react-query";
import { listModels } from "@/lib/api";

export function useModelRegistry() {
  return useQuery({
    queryKey: ["models"],
    queryFn: () => listModels(),
    staleTime: 5 * 60 * 1000,
  });
}
