# Headroom — Context Compression Integration for Consultaion

> Source: [headroomlabs-ai/headroom](https://github.com/headroomlabs-ai/headroom)  
> License: Apache 2.0

## Why use Headroom here
- Cuts tool/log/RAG/chunk tokens by 47–92%.
- Preserves debater/architect quality: same judgment, same final answer.
- Adds reversible caching (CCR): compressed on wire, recoverable original on demand.
- Adds MCP server so Hermes can call compression directly.

Candidates for immediate wins:
- Debate transcripts / seed packages in the 7 modes.
- Logs from Celery workers and orchestrator.
- RAG chunks from doc retrieval before judge synthesis.
- `Consultaion` frontend SSE payloads when verbose.

## Install
```bash
# system install is blocked on Kali
python -m venv ~/.venvs/headroom
~/.venvs/headroom/bin/pip install -U "headroom-ai[all]"
# CLI: ~/.venvs/headroom/bin/headroom
# MCP server: headroom mcp start
```

## Integration plan

### 1. Library usage for hot paths
```python
from headroom import compress

compressed = compress(context_messages)
```
Use in:
- pipeline/core/orchestrator before sending to judge
- clients/ws payload compressor for streaming output

### 2. Proxy / MCP for cross-stack compression
- Proxy mode keeps Hermes-native calls unchanged.
- MCP tools: `headroom_compress`, `headroom_retrieve`, `headroom_stats`.

### 3. Hermes wiring
- Install MCP server pointing to local headroom binary.
- Use compressed responses when querying `Consultaion` codebase through Hermes to extend context budget.

## Verification TODOs
- [ ] Record baseline token usage on a sample debate transcript.
- [ ] Run `headroom perf` after wiring proxy in dev.
- [ ] Add CI step measuring per-request token delta.

## Useful next reads
- headroom README bench values: `GSM8K / TruthfulQA / SQuAD / BFCL`.
- Proxy + agent wrap matrix: Claude Code / Codex / OpenCode all supported.
