# Task 2: The Documentation Agent

## Overview
Build an agentic loop that allows the LLM to use tools (`read_file`, `list_files`) to navigate the project wiki and answer questions with source references.

## Architecture

### Agentic Loop Flow
```
Question ──▶ LLM (with tool schemas) ──▶ tool_calls?
    │                                      │
    │ no                                   │ yes
    ▼                                      ▼
JSON output                          Execute tools
(answer + source)                        │
                                         │
                                         ▼
                                  Append tool results
                                         │
                                         ▼
                                  Back to LLM (max 10 calls)
```

### Tool Definitions

#### `read_file`
- **Purpose**: Read contents of a file from the project repository
- **Parameters**: `path` (string) - relative path from project root
- **Returns**: File contents as string, or error message
- **Security**: Block path traversal (`../`), restrict to project directory

#### `list_files`
- **Purpose**: List files and directories at a given path
- **Parameters**: `path` (string) - relative directory path from project root
- **Returns**: Newline-separated listing of entries
- **Security**: Block path traversal, restrict to project directory

## Tool Schema (OpenAI Function Calling)

```json
{
  "type": "function",
  "function": {
    "name": "read_file",
    "description": "Read a file from the project repository",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {"type": "string", "description": "Relative path from project root"}
      },
      "required": ["path"]
    }
  }
}
```

```json
{
  "type": "function",
  "function": {
    "name": "list_files",
    "description": "List files and directories at a given path",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {"type": "string", "description": "Relative directory path from project root"}
      },
      "required": ["path"]
    }
  }
}
```

## System Prompt Strategy

The system prompt instructs the LLM to:
1. Use `list_files` to discover wiki files when needed
2. Use `read_file` to read relevant documentation
3. Include source references (file path + section anchor) in answers
4. Call tools iteratively until it has enough information
5. Provide a final answer with the `source` field

## Implementation Steps

1. **Define tool functions** in `agent.py`:
   - `read_file(path: str) -> str`
   - `list_files(path: str) -> str`
   - Path validation to prevent directory traversal

2. **Define tool schemas** for LLM function calling

3. **Implement agentic loop**:
   - Send question + tool schemas to LLM
   - Parse response for `tool_calls`
   - Execute tools, collect results
   - Append tool results as `tool` role messages
   - Loop until no more tool calls or max 10 calls reached
   - Extract final answer and source from LLM response

4. **Update output format**:
   ```json
   {
     "answer": "...",
     "source": "wiki/git-workflow.md#resolving-merge-conflicts",
     "tool_calls": [
       {"tool": "list_files", "args": {"path": "wiki"}, "result": "..."},
       {"tool": "read_file", "args": {"path": "wiki/git-workflow.md"}, "result": "..."}
     ]
   }
   ```

5. **Write regression tests**:
   - Test merge conflict question → expects `read_file`, source contains `wiki/git-workflow.md`
   - Test wiki files question → expects `list_files` in tool_calls

## Security Considerations

- Validate paths to prevent directory traversal attacks
- Reject paths containing `..` or starting with `/`
- Ensure all file access is within project root directory
- Handle errors gracefully (file not found, permission denied)

## Error Handling

- Tool execution errors → return error message as tool result
- LLM API errors → exit with error code
- Path security violations → return error message
- Max tool calls reached → use whatever answer is available

## Dependencies

- `httpx`: Async HTTP client (already in project)
- Standard library: `asyncio`, `json`, `os`, `sys`, `pathlib`
