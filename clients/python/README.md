# consultaion-sdk

Official Python SDK for the Consultaion API.

## Installation

```bash
pip install consultaion-sdk
```

## Quick Start

```python
import asyncio
from consultaion import ConsultaionClient

async def main():
    # Initialize the client
    async with ConsultaionClient(
        base_url="https://api.consultaion.com",
        api_key="your-api-key",  # Optional: for API key auth
    ) as client:
        # Create a debate with smart routing
        debate = await client.create_debate({
            "prompt": "What are the pros and cons of remote work?",
            "routing_policy": "router-smart",  # or 'router-deep' for quality-focused
        })
        
        print(f"Debate created: {debate['id']}")
        
        # Get debate status
        status = await client.get_debate(debate["id"])
        print(f"Status: {status['status']}")
        
        # Stream events (Server-Sent Events)
        async for event in client.stream_events(debate["id"]):
            print(f"Event: {event['type']}", event["data"])

# Run the async function
asyncio.run(main())
```

## API Reference

### `ConsultaionClient`

#### Constructor

```python
ConsultaionClient(
    base_url: str,
    api_key: str | None = None,
    timeout: float = 30.0,
    **httpx_kwargs
)
```

**Parameters:**
- `base_url` (str, required): Base URL for the API
- `api_key` (str, optional): API key for authentication
- `timeout` (float, optional): Request timeout in seconds (default: 30.0)
- `**httpx_kwargs`: Additional arguments to pass to `httpx.AsyncClient`

#### Methods

##### `async create_debate(options: DebateCreateOptions) -> Debate`

Create a new debate.

**Parameters:**
- `options` (dict): Debate creation options
  - `prompt` (str, required): The question or topic for the debate
  - `model_id` (str, optional): Explicit model ID to use (bypasses routing)
  - `routing_policy` (str, optional): Routing policy ('router-smart' or 'router-deep')
  - `config` (dict, optional): Custom debate configuration

**Returns:** Debate object (dict)

##### `async get_debate(debate_id: str) -> Debate`

Get a debate by ID.

**Returns:** Debate object (dict)

##### `async stream_events(debate_id: str) -> AsyncIterator[DebateEvent]`

Stream Server-Sent Events from a debate.

**Returns:** Async iterator yielding DebateEvent objects

## Routing

The SDK supports intelligent model routing:

```python
# Balanced routing (default)
await client.create_debate({
    "prompt": "Your question",
    "routing_policy": "router-smart",
})

# Quality-focused routing
await client.create_debate({
    "prompt": "Your question",
    "routing_policy": "router-deep",
})

# Explicit model selection (bypasses routing)
await client.create_debate({
    "prompt": "Your question",
    "model_id": "gpt4o-mini",
})
```

## Type Safety

The SDK includes full type hints using `TypedDict`:

```python
from consultaion import (
    ConsultaionClient,
    Debate,
    DebateCreateOptions,
    DebateEvent,
    RoutingCandidate,
    RoutingMeta,
)
```

Type-check your code with `mypy`:

```bash
mypy your_code.py
```

## Context Manager

Use the client as an async context manager for automatic cleanup:

```python
async with ConsultaionClient(base_url="...") as client:
    debate = await client.create_debate({"prompt": "..."})
    # Client will be automatically closed after the block
```

Or manage the lifecycle manually:

```python
client = ConsultaionClient(base_url="...")
try:
    debate = await client.create_debate({"prompt": "..."})
finally:
    await client.close()
```

## Requirements

- Python 3.8+
- `httpx>=0.25.0`

## License

MIT
