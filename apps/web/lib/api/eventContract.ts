export interface DomainEventBase {
  type: string;
  timestamp?: string;
}

export interface MessageEvent extends DomainEventBase {
  type: "message";
  role: "agent" | "critic" | "judge" | "synthesizer";
  agent_name: string;
  content: string;
  model?: string;
}

export interface SeatMessageEvent extends DomainEventBase {
  type: "seat_message";
  seat_index: number;
  agent_name: string;
  content: string;
  role: "agent" | "critic" | "judge" | "synthesizer";
}

export interface ScoreEvent extends DomainEventBase {
  type: "score";
  agent_name: string;
  criterion: string;
  value: number;
  max_value?: number;
}

export interface ArenaResponseEvent extends DomainEventBase {
  type: "arena_response";
  agent_name: string;
  content: string;
  round: number;
}

export interface FinalEvent extends DomainEventBase {
  type: "final";
  summary?: string;
  winner?: string;
  scores?: Record<string, number>;
  meta?: {
    ranking?: string[];
    vote?: { method?: string };
    truncated?: boolean;
    truncate_reason?: string;
  };
}

export interface ErrorEvent extends DomainEventBase {
  type: "error";
  error_code?: string;
  message: string;
  retryable?: boolean;
}

export interface HeartbeatEvent extends DomainEventBase {
  type: "heartbeat";
}

export interface ProgressEvent extends DomainEventBase {
  type: "progress";
  stage: string;
  percent?: number;
}

export interface StageStartEvent extends DomainEventBase {
  type: "stage_start";
  stage: string;
}

export interface StageEndEvent extends DomainEventBase {
  type: "stage_end";
  stage: string;
}

export interface RoundStartedEvent extends DomainEventBase {
  type: "round_started";
  round?: number;
}

export type DomainEvent =
  | MessageEvent
  | SeatMessageEvent
  | ScoreEvent
  | ArenaResponseEvent
  | FinalEvent
  | ErrorEvent
  | HeartbeatEvent
  | ProgressEvent
  | StageStartEvent
  | StageEndEvent
  | RoundStartedEvent;

export interface SSEEnvelope<T extends DomainEvent = DomainEvent> {
  sequence?: number;
  type: T["type"];
  payload: T;
  emitted_at?: string;
}

const KNOWN_EVENT_TYPES = new Set<string>([
  "message",
  "seat_message",
  "score",
  "arena_response",
  "final",
  "error",
  "heartbeat",
  "progress",
  "stage_start",
  "stage_end",
  "round_started",
]);

function assertNever(value: never): never {
  throw new Error(`Unhandled event type: ${JSON.stringify(value)}`);
}

export function normalizeSSEEnvelope(raw: unknown): DomainEvent | null {
  if (!raw || typeof raw !== "object") return null;

  const obj = raw as Record<string, unknown>;
  const payload = (obj.payload ?? obj) as Record<string, unknown>;
  const type = (payload.type ?? obj.type) as string | undefined;

  if (!type || !KNOWN_EVENT_TYPES.has(type)) return null;

  return payload as unknown as DomainEvent;
}

export function assertEventTypeExhaustive(event: DomainEvent): void {
  switch (event.type) {
    case "message":
    case "seat_message":
    case "score":
    case "arena_response":
    case "final":
    case "error":
    case "heartbeat":
    case "progress":
    case "stage_start":
    case "stage_end":
    case "round_started":
      break;
    default:
      assertNever(event as never);
  }
}

export function isTerminalEvent(event: DomainEvent): event is FinalEvent {
  return event.type === "final";
}

export function isErrorEvent(event: DomainEvent): event is ErrorEvent {
  return event.type === "error";
}

export function isHeartbeatEvent(event: DomainEvent): event is HeartbeatEvent {
  return event.type === "heartbeat";
}
