# Agent CLI

A Python CLI program that connects to an LLM and answers questions using tools to navigate project documentation. This is an agentic system with a tool-execution loop.

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
   - Go back to step 1 (max 10 iterations)
3. If LLM responds with text only:
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
- `source` (string): Reference to the wiki section that answers the question
- `tool_calls` (array): All tool calls made during the agentic loop

All debug/progress output goes to stderr. Only valid JSON goes to stdout.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (missing argument, API error, timeout, etc.) |

## Tools

The agent has two tools for navigating the project documentation:

### `read_file`

Read the contents of a file from the project repository.

**Parameters:**
- `path` (string, required): Relative path from project root (e.g., `wiki/git-workflow.md`)

**Returns:** File contents as a string, or an error message if the file doesn't exist.

**Security:** Path traversal is blocked. Paths containing `..` or starting with `/` are rejected.

### `list_files`

List files and directories at a given path in the project repository.

**Parameters:**
- `path` (string, required): Relative directory path from project root (e.g., `wiki`)

**Returns:** Newline-separated listing of entries, or an error message.

**Security:** Path traversal is blocked. Only paths within the project directory are allowed.

## System Prompt

The system prompt instructs the LLM to:

1. Use `list_files` to discover what files are available in the wiki/ directory
2. Use `read_file` to read relevant documentation files
3. Always include a source reference in the answer (file path and section anchor)
4. Call tools iteratively until enough information is gathered
5. Provide concise, accurate answers based on the documentation read

## Error Handling

- **Missing argument**: Prints usage to stderr, exits with code 1
- **Missing env vars**: Prints error to stderr, exits with code 1
- **API timeout (>60s)**: Prints error to stderr, exits with code 1
- **API error**: Prints error to stderr, exits with code 1
- **Parse error**: Prints error to stderr, exits with code 1
- **Max tool calls (10)**: Returns best available answer

## Implementation Details

### Components

1. **Environment Loading**: Reads `.env.agent.secret` for API credentials
2. **Tool Functions**: `read_file()` and `list_files()` with path validation
3. **Tool Schemas**: OpenAI-compatible function calling schemas
4. **LLM Client**: Uses `httpx` for async HTTP requests
5. **Agentic Loop**: Iteratively calls LLM, executes tools, feeds results back
6. **Source Extraction**: Parses answer text or tool calls to identify source reference

### Dependencies

- `httpx`: Async HTTP client (already in project dependencies)
- Standard library: `asyncio`, `json`, `os`, `sys`, `pathlib`, `re`

## Testing

Run the regression tests:

```bash
uv run pytest tests/test_agent.py -v
```

Tests verify:
- Valid JSON output with required fields
- Tool calls are populated when tools are used
- Source field contains wiki file reference

## Future Work

- Add more tools (search, code execution, etc.)
- Improve source extraction with better section anchor detection
- Add caching for frequently accessed files
- Support for multiple documentation sources
