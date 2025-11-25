# Debate Pipeline Architecture

This document describes the modular architecture for debate orchestration introduced in Patchset 34.0. The new design separates concerns into discrete stages, state management, and execution logic, enabling easier testing and extensibility.

## Core Modules (`apps/api/orchestration/`)

The orchestration logic is split into the following components:

*   **`DebateRunner` (`engine.py`)**: The main entry point for executing a debate. It initializes the pipeline, manages the overall execution flow, handles top-level error catching, and ensures the final debate state is persisted and logged.
*   **`DebateStateManager` (`state.py`)**: Responsible for all database interactions. It abstracts the persistence of `Debate`, `DebateRound`, `Message`, `Score`, and `Vote` records, keeping the execution logic free of direct DB calls.
*   **`StandardDebatePipeline` (`pipeline.py`)**: Defines the standard sequence of stages for a debate. It implements the `DebatePipeline` interface.
*   **Stages (`stages.py`)**: Concrete implementations of the `DebateStage` interface. Each stage performs a specific unit of work:
    *   `DraftStage`: Generates initial candidate responses from agents.
    *   `CritiqueStage`: Facilitates cross-critique and revision of candidates.
    *   `JudgeStage`: Collects scores and rationales from judge personas.
    *   `SynthesisStage`: Synthesizes the final answer based on the best candidates.
*   **`FinalizationService` (`finalization.py`)**: A helper service for computing rankings (Borda/Condorcet) and persisting final vote results.
*   **`DebateContext` & `DebateState` (`interfaces.py`)**: Data structures for passing data through the pipeline. `Context` is immutable configuration; `State` is mutable execution state.

## Default Stage Order

The `StandardDebatePipeline` executes stages in the following order:

1.  **Draft**: Agents generate initial answers to the prompt.
2.  **Critique**: Agents critique each other's drafts and revise their own.
3.  **Judge**: Judges score the revised candidates.
4.  **Synthesis**: The best candidates are selected and synthesized into a final answer.

## Configuration (`apps/api/parliament/config.py`)

Hardcoded prompts and round definitions have been moved to `apps/api/parliament/config.py`. This file contains:

*   `PARLIAMENT_CHARTER`: The system prompt for parliament seats.
*   `SEAT_OUTPUT_CONTRACT`: The JSON schema instruction for seat outputs.
*   `DEFAULT_ROUNDS`: The definition of rounds for parliamentary debates (Explore, Rebuttal, Converge).

This centralization allows for easier tuning of prompts and debate structure without modifying the core engine code.

## Execution Sequence

A typical debate run follows this sequence:

1.  **API Call**: `POST /debates` creates a `Debate` record (status: `queued`) and triggers a background task.
2.  **Dispatch**: The background task calls `orchestrator.run_debate`.
3.  **Initialization**:
    *   `DebateStateManager` is initialized.
    *   `DebateContext` is built from the debate configuration.
    *   `StandardDebatePipeline` and `DebateRunner` are instantiated.
4.  **Pipeline Execution** (`runner.run()`):
    *   **Draft Stage**: Calls LLMs for each agent. Persists messages. Publishes SSE events.
    *   **Critique Stage**: Calls LLMs for critique/revision. Persists revisions. Publishes SSE events.
    *   **Judge Stage**: Calls LLMs for scoring. Persists scores. Computes rankings via `FinalizationService`. Publishes SSE events.
    *   **Synthesis Stage**: Selects top candidates. Calls LLM for synthesis. Updates state with final content.
5.  **Completion**:
    *   `DebateRunner` marks the debate as `completed` via `DebateStateManager`.
    *   Usage stats are recorded.
    *   `debate.completed` event is logged.
    *   Final SSE event is published.
