/**
 * Patchset 148 G1: Live Page State Extraction.
 *
 * Provides a specialized hook for Arena Run pages to extract semantic
 * session state from the raw workspace streams. Reduces prop drilling
 * and logic duplication in LiveArenaPage / ArenaRunView.
 */
import { useRunWorkspace } from "@/hooks/useRunWorkspace";
import { isTerminalRunStatus } from "@/lib/runStatus";

export function useArenaSession(debateId: string) {
  const workspace = useRunWorkspace(debateId);

  const isTerminal = isTerminalRunStatus(workspace.debate?.status);
                     
  const hasSynthesis = workspace.debate?.synthesis_status === "succeeded" ||
                       workspace.debate?.synthesis_report != null ||
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
