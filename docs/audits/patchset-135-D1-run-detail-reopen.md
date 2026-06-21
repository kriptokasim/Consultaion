# Patchset 135 — Track D Reopen Note

**Date:** 2026-06-21
**Topic:** Frontend View Decomposition

In Patchset 134, finding 134-D1 correctly identified that `RunDetailClient.tsx` was 798 lines and needed decomposition. That finding was marked as "Fixed" because the type safety and event contracts were resolved, but the file size was NOT reduced.

For Patchset 135, we are taking a phased approach to decomposition:
1. We are creating a new suite of shared presentation components (`RunViewShell`, `RunHeader`, `ModelCardGrid`, `EventTimeline`).
2. We will use these new shared components to construct the new `<CodingAgentView>` within a strict <200 line limit.
3. **Important**: We are *not* proactively refactoring the legacy `RunDetailClient.tsx` to use the new shell in this patchset to limit regression risk on the existing Debate/Arena views. The legacy view will be migrated in a future patchset once the `RunViewShell` proves stable in the Coding Agent mode.

**Update (End of Patchset 135):**
The shared components (`RunViewShell`, `RunHeader`, `ModelCardGrid`, `EventTimeline`) have been successfully implemented and deployed for the Coding Agent mode (`/coding-agent/[id]`). 

**Remaining Work for Future Patchset:**
- Refactor `apps/web/app/(app)/debates/[debateId]/RunDetailClient.tsx` to consume the new `RunViewShell` primitives.
- Remove redundant CSS classes and inline styles from `RunDetailClient.tsx` once the shell is adopted.
