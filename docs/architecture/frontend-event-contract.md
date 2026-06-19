# Frontend Event Contract

## Overview

The frontend uses typed SSE envelopes and domain events to ensure compile-time safety for all real-time data flows.

## SSE Envelope

```typescript
interface SSEEnvelope<T extends DomainEvent = DomainEvent> {
  sequence?: number;
  type: T["type"];
  payload: T;
  emitted_at?: string;
}
```

## Domain Events

```typescript
type DomainEvent =
  | MessageEvent
  | SeatMessageEvent
  | ScoreEvent
  | ArenaResponseEvent
  | FinalEvent
  | ErrorEvent
  | HeartbeatEvent
  | ProgressEvent
  | StageStartEvent
  | StageEndEvent;
```

## Normalization

All SSE consumers use `normalizeSSEEnvelope()` to convert raw data to typed events. No component inspects raw envelopes directly.

```typescript
const event = normalizeSSEEnvelope(rawData);
if (event) {
  switch (event.type) {
    case "message": handleMessage(event); break;
    case "final": handleFinal(event); break;
    // ...
  }
}
```

## Exhaustiveness Checking

Event switches use `assertEventTypeExhaustive()` to ensure all event types are handled:

```typescript
function assertNever(value: never): never {
  throw new Error(`Unhandled event type: ${JSON.stringify(value)}`);
}
```

## Error Events

Error events carry typed error information:

```typescript
interface ErrorEvent extends DomainEventBase {
  type: "error";
  error_code?: string;
  message: string;
  retryable?: boolean;
}
```

## No `as any` in Critical Paths

Critical SSE paths must not use `as any`. The only acceptable escape is `unknown` plus runtime validation for untrusted data.
