/**
 * Patchset 148 G1: Live Page State Extraction.
 *
 * Provides a specialized hook for Arena Run pages to extract semantic
 * session state from the raw workspace streams. Reduces prop drilling
 * and logic duplication in LiveArenaPage / ArenaRunView.
 */
import { useRunWorkspace } from "@/hooks/useRunWorkspace";

export function useArenaSession(debateId: string) {
  const workspace = useRunWorkspace(debateId, true); // true = hydrate

  const isTerminal = workspace.debate?.status === "completed" || 
                     workspace.debate?.status === "completed_budget" ||
                     workspace.debate?.status === "failed";
                     
  const hasSynthesis = workspace.debate?.synthesis_status === "completed" ||
                       workspace.events.some(e => e.type === "arena_synthesis");

  const expectedModelsCount = workspace.debate?.models_expected ||
                              workspace.debate?.final_meta?.models?.length ||
                              2;

  return {
    ...workspace,
    isTerminal,
    hasSynthesis,
    expectedModelsCount,
  };
}
