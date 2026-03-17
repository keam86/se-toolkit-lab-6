# Agent CLI

A Python CLI program that connects to an LLM and answers questions. This is the foundation for the agentic system.

## Architecture

```
┌─────────────┐     ┌───────────┐     ┌─────────────┐     ┌──────────┐
│   User      │────▶│  agent.py │────▶│  LLM API    │────▶│  JSON    │
│  Question   │     │   CLI     │     │  (Qwen)     │     │  Output  │
└─────────────┘     └───────────┘     └─────────────┘     └──────────┘
```

## LLM Provider

**Provider**: Qwen Code API (via local proxy)

| Setting | Value |
|---------|-------|
| Base URL | `http://10.93.25.111:42005/v1` |
| Model | `qwen3-coder-plus` |
| API | OpenAI-compatible chat completions |

### Why Qwen Code?

- Works from Russia without restrictions
- 1000 free requests per day
- No credit card required
- Strong reasoning capabilities
- OpenAI-compatible API

## Configuration

Create `.env.agent.secret` from the example:

```bash
cp .env.agent.example .env.agent.secret
```

Edit `.env.agent.secret`:

```bash
# Your LLM provider API key
LLM_API_KEY=your-api-key-here

# API base URL (OpenAI-compatible endpoint)
LLM_API_BASE=http://10.93.25.111:42005/v1

# Model name
LLM_MODEL=qwen3-coder-plus
```

## Usage

```bash
# Run with a question
uv run agent.py "What does REST stand for?"

# Example output
{"answer": "Representational State Transfer.", "tool_calls": []}
```

## Output Format

The agent outputs a single JSON line to stdout:

```json
{
  "answer": "The LLM's response text",
  "tool_calls": []
}
```

- `answer` (string): The LLM's answer to the question
- `tool_calls` (array): Empty for now, will be populated in Task 2 when tools are added

All debug/progress output goes to stderr. Only valid JSON goes to stdout.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (missing argument, API error, timeout, etc.) |

## Error Handling

- **Missing argument**: Prints usage to stderr, exits with code 1
- **Missing env vars**: Prints error to stderr, exits with code 1
- **API timeout (>60s)**: Prints error to stderr, exits with code 1
- **API error**: Prints error to stderr, exits with code 1
- **Parse error**: Prints error to stderr, exits with code 1

## Implementation Details

### Components

1. **Environment Loading**: Reads `.env.agent.secret` for API credentials
2. **LLM Client**: Uses `httpx` for async HTTP requests to the chat completions endpoint
3. **Response Parsing**: Extracts the answer from `choices[0].message.content`
4. **JSON Output**: Formats and prints the result as a single JSON line

### Dependencies

- `httpx`: Async HTTP client (already in project dependencies)
- Standard library: `asyncio`, `json`, `os`, `sys`, `pathlib`

## Testing

Run the regression test:

```bash
uv run pytest backend/tests/unit/test_agent.py -v
```

## Future Work (Tasks 2-3)

- Add tool calling support
- Implement agentic loop
- Add domain-specific knowledge via system prompt
