const fs = require('fs');
let code = fs.readFileSync('apps/web/hooks/useRunWorkspace.ts', 'utf8');

// 1. Add Import
code = code.replace(
  `import { streamingReducer, INITIAL_STREAMING_STATE, selectMergedResponses } from "@/lib/workspace/streamReducer";\nimport type { StreamingState } from "@/lib/workspace/streamReducer";`,
  `import { streamingReducer, INITIAL_STREAMING_STATE, selectMergedResponses } from "@/lib/workspace/streamReducer";\nimport type { StreamingState } from "@/lib/workspace/streamReducer";\nimport { connectionReducer, INITIAL_CONNECTION_STATE } from "@/lib/workspace/connectionReducer";`
);

// 2. Remove decoupled state variables
code = code.replace(/const \[isPollingFallback, setIsPollingFallback\] = useState\(false\);\n/, '');
code = code.replace(/const \[hydrationQuality, setHydrationQuality\] = useState<RunHydrationQuality>\("complete"\);\n/, '');
code = code.replace(/const \[timelineError, setTimelineError\] = useState<string \| null>\(null\);\n/, '');
code = code.replace(/const \[eventsError, setEventsError\] = useState<string \| null>\(null\);\n/, '');
code = code.replace(/const \[coreState, setCoreState\] = useState<CoreState>\("idle"\);\n/, '');
code = code.replace(/const \[responsesState, setResponsesState\] = useState<ResponsesState>\("idle"\);\n/, '');
code = code.replace(/const \[responsesError, setResponsesError\] = useState<string \| null>\(null\);\n/, '');
code = code.replace(/const \[timelineState, setTimelineState\] = useState<TimelineState>\("idle"\);\n/, '');
code = code.replace(/const \[coreErrorCode, setCoreErrorCode\] = useState<CoreLoadFailure \| null>\(null\);\n/, '');
code = code.replace(/const \[coreHttpStatus, setCoreHttpStatus\] = useState<number \| null>\(null\);\n/, '');
// Notice: `error` is left because it's a generic workspace error, wait, connectionReducer has `error`. We'll keep `error` as is for generic errors not handled by core.

// 3. Add useReducer
code = code.replace(
  `const \[error, setError\] = useState<string \| null>\(null\);\n`,
  `const [error, setError] = useState<string | null>(null);\n  const [connState, dispatchConn] = useReducer(connectionReducer, INITIAL_CONNECTION_STATE);\n  const { coreState, responsesState, responsesError, timelineState, coreErrorCode, coreHttpStatus, hydrationQuality, timelineError, eventsError, isPollingFallback } = connState;\n`
);

// 4. Replace setCoreState
code = code.replace(/setCoreState\("loading"\);/g, 'dispatchConn({ type: "HYDRATION_START" });');
code = code.replace(/setCoreState\("ready"\);/g, 'dispatchConn({ type: "CORE_LOADED", isTerminal });');
code = code.replace(/setCoreState\("failed"\);/g, '// handled by CORE_FAILED\n');

code = code.replace(/setCoreErrorCode\(null\);/g, '');
code = code.replace(/setCoreHttpStatus\(null\);/g, '');
code = code.replace(/setCoreErrorCode\(code\);/g, 'dispatchConn({ type: "CORE_FAILED", code, httpStatus, error: msg });');
code = code.replace(/setCoreErrorCode\((.*?)\);/g, '/* replaced */');
code = code.replace(/setCoreHttpStatus\((.*?)\);/g, '/* replaced */');

code = code.replace(/setResponsesState\("idle"\);/g, '');
code = code.replace(/setResponsesState\("loading"\);/g, 'dispatchConn({ type: "RESPONSES_LOADING" });');
code = code.replace(/setResponsesState\("empty"\);/g, ''); // Handled by loaded count=0
code = code.replace(/setResponsesState\("ready"\);/g, ''); // Handled by loaded count>0
code = code.replace(/setResponsesState\(responsesData.items.length > 0 \? "ready" : "empty"\);/g, 'dispatchConn({ type: "RESPONSES_LOADED", count: responsesData.items.length });');

code = code.replace(/setResponsesState\("deployment_mismatch"\);/g, 'dispatchConn({ type: "RESPONSES_FAILED", isMismatch: true, error: "Backend contract mismatch — /responses endpoint unavailable" });');
code = code.replace(/setResponsesState\("failed"\);/g, 'dispatchConn({ type: "RESPONSES_FAILED", isMismatch: false, error: err?.message || "Failed to load persisted responses" });');

code = code.replace(/setTimelineState\("idle"\);/g, '');
code = code.replace(/setTimelineState\("loading"\);/g, 'dispatchConn({ type: "TIMELINE_LOADING" });');
code = code.replace(/setTimelineState\("failed"\);/g, 'dispatchConn({ type: "TIMELINE_FAILED" });');

code = code.replace(/setTimelineState\(result.quality === "debate_only" \? "failed" : result.quality === "events_fallback" \? "degraded" : "ready"\);/g, '');
code = code.replace(/setHydrationQuality\(result.quality\);/g, 'dispatchConn({ type: "TIMELINE_LOADED", quality: result.quality, timelineError: result.timelineError, eventsError: result.eventsError });');
code = code.replace(/setTimelineError\(result.timelineError\);/g, '');
code = code.replace(/setEventsError\(result.eventsError\);/g, '');

code = code.replace(/setIsPollingFallback\(true\);/g, 'dispatchConn({ type: "START_POLLING" });');
code = code.replace(/setIsPollingFallback\(false\);/g, 'dispatchConn({ type: "STOP_POLLING" });');

code = code.replace(/setResponsesError\((.*?)\);/g, '');
code = code.replace(/setTimelineError\(null\);/g, '');
code = code.replace(/setEventsError\(null\);/g, '');
code = code.replace(/setHydrationQuality\("complete"\);/g, '');

code = code.replace(/let status: RunWorkspaceStatus = "idle";[\s\S]*?} else if \(error\) {\n    status = "error";\n  }/, 'const status = connState.status;');

fs.writeFileSync('apps/web/hooks/useRunWorkspace.ts', code);
