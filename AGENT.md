# Agent CLI

A Python CLI program that connects to an LLM and answers questions using tools to navigate project documentation, query the backend API, and analyze source code. This is an agentic system with a tool-execution loop.

## Architecture

### Agentic Loop Flow

```
┌─────────────┐     ┌───────────┐     ┌─────────────┐
│   User      │────▶│  agent.py │────▶│  LLM API    │
│  Question   │     │   CLI     │     │  (Qwen)     │
└─────────────┘     └───────────┘     └─────────────┘
                          │                   │
                          │                   ▼
                          │           ┌─────────────┐
                          │           │ tool_calls? │
                          │           └─────────────┘
                          │              │        │
                          │              │ yes    │ no
                          │              ▼        ▼
                          │     ┌─────────────┐  │
                          │     │ Execute     │  │
                          │     │ tools       │  │
                          │     └─────────────┘  │
                          │              │       │
                          │              └───────┤
                          │                      │
                          ▼                      ▼
                    ┌─────────────────────────────────┐
                    │  JSON Output                    │
                    │  {answer, source, tool_calls}   │
                    └─────────────────────────────────┘
```

### Loop Steps

1. Send user question + tool schemas to LLM
2. If LLM responds with `tool_calls`:
   - Execute each tool
   - Append results as `tool` role messages
   - Go back to step 1 (max 12 iterations)
3. If LLM responds with text only:
   - Check if it's a real answer or "let me continue"
   - If incomplete, force final answer without tools
   - Extract answer and source
   - Output JSON and exit

## LLM Provider

**Provider**: Qwen Code API (via local proxy)

| Setting | Value |
|---------|-------|
| Base URL | `http://10.93.25.111:42005/v1` |
| Model | `qwen3-coder-plus` |
| API | OpenAI-compatible chat completions with function calling |

## Configuration

The agent reads configuration from environment variables:

| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` or env |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` or env |
| `LLM_MODEL` | Model name | `.env.agent.secret` or env |
| `LMS_API_KEY` | Backend API key for query_api | `.env.docker.secret` or env |
| `AGENT_API_BASE_URL` | Base URL for query_api (default: `http://localhost:42002`) | Environment or default |

**Important:** Two distinct keys:
- `LMS_API_KEY` (in `.env.docker.secret`) - protects backend endpoints
- `LLM_API_KEY` (in `.env.agent.secret`) - authenticates with LLM provider

## Usage

```bash
# Run with a question
uv run agent.py "How do you resolve a merge conflict?"

# Example output
{
  "answer": "To resolve a merge conflict, edit the file to choose which version to keep...",
  "source": "wiki/git.md#merge-conflict",
  "tool_calls": [
    {"tool": "list_files", "args": {"path": "wiki"}, "result": "..."},
    {"tool": "read_file", "args": {"path": "wiki/git.md"}, "result": "..."}
  ]
}
```

## Output Format

The agent outputs a single JSON line to stdout:

```json
{
  "answer": "The LLM's response text",
  "source": "wiki/file.md#section-anchor",
  "tool_calls": [
    {
      "tool": "tool_name",
      "args": {"arg1": "value1"},
      "result": "Tool execution result"
    }
  ]
}
```

- `answer` (string): The LLM's answer to the question
- `source` (string, optional): Reference to the wiki/source file that answers the question
- `tool_calls` (array): All tool calls made during the agentic loop

All debug/progress output goes to stderr. Only valid JSON goes to stdout.

## Tools

The agent has three tools:

### `read_file`

Read the contents of a file from the project repository.

**Parameters:**
- `path` (string, required): Relative path from project root

**Security:** Path traversal is blocked.

### `list_files`

List files and directories at a given path.

**Parameters:**
- `path` (string, required): Relative directory path

**Security:** Path traversal is blocked.

### `query_api`

Call the deployed backend API with optional authentication.

**Parameters:**
- `method` (string, required): HTTP method (GET, POST, PUT, DELETE, PATCH)
- `path` (string, required): API path
- `body` (string, optional): JSON request body
- `use_auth` (boolean, optional): Whether to include auth header (default: true)

**Authentication:** Uses `LMS_API_KEY` from environment.

## System Prompt Strategy

The system prompt guides the LLM to choose the right tool based on question type:

1. **Wiki/documentation questions** → `list_files` + `read_file` on wiki/
2. **Source code questions** → `list_files` + `read_file` on backend/
3. **System/data questions** → `query_api` for live data
4. **Infrastructure questions** → Read specific files (docker-compose.yml, Dockerfile, Caddyfile, run.py)
5. **Error diagnosis** → `query_api` to reproduce, then `read_file` to find bug

## Key Implementation Decisions

### Handling Incomplete LLM Responses

A significant challenge was handling cases where the LLM would respond with "Let me continue reading..." instead of providing a final answer. The solution involved:

1. **Detection**: Check if the LLM content contains phrases like "let me", "I'll", "need to read"
2. **Forced synthesis**: When detected, call the LLM again without tools and instruct it to synthesize
3. **Max iterations**: After 12 tool calls, force a final answer with explicit instructions

### Tool Schema Design

The `query_api` tool includes a `use_auth` parameter to support testing unauthenticated access (e.g., "What status code without auth?"). This was essential for question 6 in the benchmark.

### Environment Variable Loading

The agent loads from both `.env.agent.secret` (LLM config) and `.env.docker.secret` (LMS API key), with environment variable overrides. This supports both local development and autochecker evaluation.

## Error Handling

- **Missing argument**: Prints usage to stderr, exits with code 1
- **Missing env vars**: Prints error to stderr, exits with code 1
- **API timeout (>60s)**: Prints error to stderr, exits with code 1
- **API error**: Prints error to stderr, exits with code 1
- **Parse error**: Prints error to stderr, exits with code 1
- **Max tool calls (12)**: Forces final answer synthesis

## Benchmark Performance

The agent passes all 10 local benchmark questions:

| # | Question Type | Tools Used |
|---|---------------|------------|
| 1 | Wiki: branch protection | read_file |
| 2 | Wiki: SSH connection | read_file |
| 3 | Source: framework | read_file |
| 4 | Source: router modules | list_files, read_file |
| 5 | Data: item count | query_api |
| 6 | System: status code | query_api (use_auth=false) |
| 7 | Error: ZeroDivisionError | query_api, read_file |
| 8 | Error: TypeError | query_api, read_file |
| 9 | Infrastructure: request journey | read_file (multiple) |
| 10 | Pipeline: idempotency | read_file |

## Lessons Learned

1. **LLM non-determinism**: The same question can produce different tool call sequences. The agent must be robust to this.

2. **Tool descriptions matter**: Clear, specific tool descriptions help the LLM choose the right tool.

3. **Forced synthesis is essential**: Without logic to detect and handle "let me continue" responses, the agent would fail on complex questions.

4. **Max iterations tuning**: Too few (8) caused premature termination; too many (12+) wasted tokens. 12 is a good balance.

5. **Authentication flexibility**: The `use_auth` parameter was critical for testing unauthenticated API behavior.

## Testing

Run the regression tests:

```bash
uv run pytest tests/test_agent.py -v
```

Run the benchmark:

```bash
uv run run_eval.py
```

## Dependencies

- `httpx`: Async/sync HTTP client
- Standard library: `asyncio`, `json`, `os`, `sys`, `pathlib`, `re`
