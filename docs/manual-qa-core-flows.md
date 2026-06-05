# Manual QA Core Flows - Verification Guide

This guide outlines the step-by-step procedures for manually verifying the primary user flows and modes of the Consultaion platform.

---

## 1. Arena Run Flow (Arena-First Live Flow)
**Goal:** Verify multi-model SOTA analysis, streaming response rendering, and the synthesis summary using the primary Arena-first `/live` entry point.

1. Navigate directly to the live Arena page (e.g., `/live`).
2. Verify that the input prompt area is visible and default SOTA models are pre-selected.
3. Type a complex prompt (e.g., `"Should we build a web application in Next.js or pure HTML?"`).
4. Click **Start Arena Run** (or press Enter).
5. **Expected Behavior:**
   - The UI transitions to the active run state.
   - SOTA models start generating in parallel.
   - Tab buttons for the SOTA models (`GPT-4o`, `Claude 3.5 Sonnet`, `Gemini 2.5 Pro`, `DeepSeek R1`) appear.
   - On mobile, only the active model card is rendered with tab selection. On desktop, they render in a clean grid layout.
   - Once all models finish, the **Synthesis Card** renders at the bottom.
   - Verify that there is no horizontal text overflow or broken markdown layout.

---

## 2. Compare Run Flow
**Goal:** Verify side-by-side comparison of selected models.

1. Navigate to `/live` (or the sidebar/navigation panel) and select **Compare** mode.
2. Under the model selection list, pick two or more models (e.g., `GPT-4o Mini` and `Claude 3 Haiku`).
3. Enter a prompt and click **Compare**.
4. **Expected Behavior:**
   - The UI loads a horizontal scroll list containing the selected models' cards.
   - Responses stream in parallel.
   - Code blocks and text wrap correctly. You can scroll horizontally to compare responses, but individual cards do not overflow or cause page-level layout breakage.

---

## 3. Conversation Run Flow (Beta)
**Goal:** Verify back-and-forth chat mode with a single model.

1. Navigate to `/live` (or the sidebar/navigation panel) and select **Conversation** (marked as Beta) mode.
2. Select a target model and input your first message.
3. Submit the message and observe the stream.
4. **Expected Behavior:**
   - A standard chat interface is displayed.
   - Messages from the user and the assistant are rendered as chat bubbles or cards.
   - Verify that the model's display name and logo are correctly rendered on each bubble.
   - Send follow-up messages to verify conversational context.

---

## 4. Debate / Parliament Run Flow (Beta)
**Goal:** Verify the multi-stage agent pipeline (Draft -> Critique -> Judge -> Synthesis).

1. Navigate to `/live` (or the sidebar/navigation panel) and select **Debate (Parliament)** (marked as Beta) mode.
2. Pick or configure the panel of agents (Optimist, Pessimist, Judge, etc.).
3. Enter a debate prompt and click **Start Debate**.
4. **Expected Behavior:**
   - The UI displays a live timeline of rounds (e.g., Round 1: Draft, Round 2: Critique, Round 3: Judgement, Round 4: Synthesis).
   - As each stage runs, messages appear in the timeline.
   - A final verdict is generated and shown.

---

## 5. Demo / Mock Mode
**Goal:** Run a fast, simulated run without incurring LLM provider costs.

1. Turn on **USE_MOCK=true** in the backend configuration or environment (if running in test/demo environment).
2. Start any run mode (Arena, Compare, or Debate).
3. **Expected Behavior:**
   - The run executes immediately using mocked model responses and mock synthesis.
   - Results are populated in 1–2 seconds.

---

## 6. Public Shared Run Flow
**Goal:** Verify public access controls, attribution tracking, and read-only behavior.

1. Create a successful Arena or Compare run.
2. Locate the **Share** button on the result view.
3. Click **Share** and toggle the run to **Public**. Copy the generated share link.
4. Open a private/incognito browser window (or log out of your current session).
5. Paste the copied share link and load the page.
6. **Expected Behavior:**
   - The run page loads without prompting for authentication.
   - The CTA banners (`PublicRunCTATop` and `PublicRunCTAFooter`) are visible.
   - All interactive controls (e.g., prompt input, settings, retry button) are disabled or hidden.
   - The user can toggle model tabs and read the responses, but cannot launch new runs.

---

## 7. Quota & Retry Flow
**Goal:** Verify credit exhaustion warnings, friendly error mapping, and retry badge note.

1. As a Free tier user, run multiple SOTA model queries until your daily credit quota is exhausted.
2. Or mock a rate limit / credit error by returning a backend error containing `hosted_credits.exhausted`.
3. Try launching another run.
4. **Expected Behavior:**
   - A friendly error banner is shown: *"Daily SOTA run quota exhausted."*
   - A helpful hint is displayed: *"Please upgrade to a Pro plan or configure your own API keys in Settings to continue."*
   - For individual model card failures, the card displays a clean error explanation and detail toggle.
   - A non-intrusive badge saying `"Retry coming soon"` is displayed instead of a broken button or a generic alert dialog.

---

## 8. Mode Status Matrix

| Mode Name | Status | Primary Purpose | QA Status |
| :--- | :--- | :--- | :--- |
| **Arena** | Active | Parallel analysis across SOTA models with synthesized verdict | Passed & Automated |
| **Compare** | Active | Side-by-side customizable model comparison | Passed & Automated |
| **Conversation** | **Beta** | Interactive conversational thread with a selected model | Automated |
| **Debate / Parliament** | **Beta** | Multi-round multi-agent debate pipeline with evaluation | Automated |

