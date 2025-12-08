# Orchestrator Resumability Design Doc

## Current Model

Currently, the debate orchestrator runs as a single, long-running async function (`dispatch_debate_run`). It executes all phases (Draft -> Critique -> Judge -> Synthesis) in one go.

### Problems

1. **No Checkpointing**: If the worker process crashes or restarts mid-run, the debate gets stuck in the "running" state indefinitely.
2. **Lack of Introspection**: It is difficult to determine exactly which phase failed without parsing logs.
3. **Resource Locking**: Long-running tasks hold onto worker slots for the entire duration.

## Proposed State Machine

We propose breaking the monolithic function into discrete steps managed by a state machine.

### Debate Phases

The `Debate` model (or a new `DebateRun` model) will track the `current_phase`:

1. `pending`: Created, waiting to start.
2. `round_1_running`: Agents generating initial arguments.
3. `round_1_complete`: Arguments generated.
4. `round_2_running`: Agents generating rebuttals/revisions.
5. `judging`: Judges evaluating the debate.
6. `synthesis`: Synthesizer generating the final summary.
7. `completed`: Successfully finished.
8. `failed`: Encountered an unrecoverable error.

### Execution Flow

Each step will be an idempotent task:

1. **Worker picks up task**: Finds a debate in a specific state.
2. **Executes logic**: Runs the LLM calls for that phase.
3. **Updates DB**: Saves results (messages, scores) and advances `current_phase`.
4. **Enqueues next step**: Triggers the next phase (or the worker loop picks it up).

### Worker Resume Loop

A background "janitor" or "resume" worker will:

1. Scan for debates in `*_running` states with `updated_at` older than a threshold (e.g., 5 minutes).
2. Attempt to resume them from the last successful checkpoint.

### Database Schema Updates (Future)

We will need to add the following fields to the `Debate` model:

- `current_phase`: Enum (as described above).
- `current_round`: Integer (to support N rounds).
- `last_step_at`: Timestamp of the last successful state transition.

## Implementation Plan

### Patchset 60.x: Schema & Basic Phases

- Add `current_phase` and `last_step_at` columns.
- Update `dispatch_debate_run` to update these fields as it progresses (checkpointing), even if it still runs in one go.

### Patchset 6x: Resume Workers

- Implement the "resume" logic to pick up stalled debates.
- Refactor `dispatch_debate_run` into smaller, composable functions for each phase.

### Patchset 6x: Telemetry

- Add metrics for how often resumes happen and at which phases failures occur.
