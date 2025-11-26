# @consultaion/sdk

Official TypeScript/JavaScript SDK for the Consultaion API.

## Installation

```bash
npm install @consultaion/sdk
```

## Quick Start

```typescript
import { ConsultaionClient } from '@consultaion/sdk';

// Initialize the client
const client = new ConsultaionClient({
  baseUrl: 'https://api.consultaion.com',
  apiKey: 'your-api-key', // Optional: for API key auth
});

// Create a debate with smart routing
const debate = await client.createDebate({
  prompt: 'What are the pros and cons of remote work?',
  routing_policy: 'router-smart', // or 'router-deep' for quality-focused
});

console.log(`Debate created: ${debate.id}`);

// Get debate status
const status = await client.getDebate(debate.id);
console.log(`Status: ${status.status}`);

// Stream events (Server-Sent Events)
const cleanup = client.streamEvents(
  debate.id,
  (event) => {
    console.log('Event:', event.type, event.data);
  },
  (error) => {
    console.error('Stream error:', error);
  }
);

// Stop streaming when done
// cleanup();
```

## API Reference

### `ConsultaionClient`

#### Constructor

```typescript
new ConsultaionClient(options: ConsultaionClientOptions)
```

**Options:**
- `baseUrl` (string, required): Base URL for the API
- `apiKey` (string, optional): API key for authentication
- `fetch` (function, optional): Custom fetch implementation

#### Methods

##### `createDebate(options: DebateCreateOptions): Promise<Debate>`

Create a new debate.

**Options:**
- `prompt` (string, required): The question or topic for the debate
- `model_id` (string, optional): Explicit model ID to use (bypasses routing)
- `routing_policy` (string, optional): Routing policy ('router-smart' or 'router-deep')
- `config` (object, optional): Custom debate configuration

**Returns:** Promise resolving to the created Debate object

##### `getDebate(id: string): Promise<Debate>`

Get a debate by ID.

**Returns:** Promise resolving to the Debate object

##### `streamEvents(id: string, onEvent: (event: DebateEvent) => void, onError?: (error: Error) => void): () => void`

Stream Server-Sent Events from a debate.

**Returns:** Cleanup function to stop streaming

## Routing

The SDK supports intelligent model routing:

```typescript
// Balanced routing (default)
await client.createDebate({
  prompt: 'Your question',
  routing_policy: 'router-smart',
});

// Quality-focused routing
await client.createDebate({
  prompt: 'Your question',
  routing_policy: 'router-deep',
});

// Explicit model selection (bypasses routing)
await client.createDebate({
  prompt: 'Your question',
  model_id: 'gpt4o-mini',
});
```

## TypeScript Support

The SDK is written in TypeScript and includes full type definitions. All types are exported:

```typescript
import type {
  ConsultaionClientOptions,
  Debate,
  DebateCreateOptions,
  DebateEvent,
} from '@consultaion/sdk';
```

## License

MIT
