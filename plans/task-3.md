# Task 3: The System Agent

## Overview
Add a `query_api` tool to the agent so it can query the deployed backend API in addition to reading documentation. This enables the agent to answer questions about system facts (framework, ports, status codes) and data-dependent queries (item count, scores).

## LLM Configuration from Environment Variables

The agent reads all configuration from environment variables:

| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for query_api auth | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for query_api (default: `http://localhost:42002`) | Optional env var |

**Important:** Two distinct keys:
- `LMS_API_KEY` (in `.env.docker.secret`) - protects backend endpoints
- `LLM_API_KEY` (in `.env.agent.secret`) - authenticates with LLM provider

## Tool Definition: `query_api`

### Schema
```json
{
  "type": "function",
  "function": {
    "name": "query_api",
    "description": "Call the deployed backend API to query data or check system behavior. Use this for questions about database contents, API responses, status codes, or system state.",
    "parameters": {
      "type": "object",
      "properties": {
        "method": {
          "type": "string",
          "description": "HTTP method (GET, POST, PUT, DELETE, etc.)",
          "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]
        },
        "path": {
          "type": "string",
          "description": "API path (e.g., '/items/', '/analytics/completion-rate')"
        },
        "body": {
          "type": "string",
          "description": "Optional JSON request body for POST/PUT/PATCH requests"
        }
      },
      "required": ["method", "path"]
    }
  }
}
```

### Implementation
```python
def tool_query_api(method: str, path: str, body: str | None = None) -> str:
    """Call the deployed backend API with authentication."""
    api_base = os.environ.get("AGENT_API_BASE_URL", "http://localhost:42002")
    api_key = os.environ.get("LMS_API_KEY")
    
    url = f"{api_base}{path}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    # Make HTTP request with httpx
    # Return JSON string with status_code and body
```

## System Prompt Updates

The system prompt must guide the LLM to choose the right tool:

1. **Use `list_files`** - to discover what files exist in a directory
2. **Use `read_file`** - to read documentation (wiki/) or source code files
3. **Use `query_api`** - to query the running backend for:
   - Database contents (item count, learner data)
   - API behavior (status codes, error responses)
   - System state (analytics, completion rates)

Example guidance:
- "For questions about what the wiki says, use read_file on wiki/*.md files"
- "For questions about the running system (database, API responses), use query_api"
- "For questions about source code (framework, routers), use read_file on backend/ files"

## Benchmark Questions

The evaluation runs 10 questions across different classes:

| # | Question | Tool(s) | Expected Answer |
|---|----------|---------|-----------------|
| 0 | Wiki: protect a branch | read_file | branch, protect |
| 1 | Wiki: SSH connection | read_file | ssh, key, connect |
| 2 | Backend framework | read_file | FastAPI |
| 3 | API router modules | list_files | items, interactions, analytics, pipeline |
| 4 | Items in database | query_api | number > 0 |
| 5 | Status code without auth | query_api | 401 or 403 |
| 6 | Completion-rate error | query_api, read_file | ZeroDivisionError |
| 7 | Top-learners crash | query_api, read_file | TypeError, None |
| 8 | Request journey (LLM judge) | read_file | Caddy → FastAPI → auth → router → ORM → PostgreSQL |
| 9 | ETL idempotency (LLM judge) | read_file | external_id check, duplicates skipped |

## Implementation Steps

1. Add `LMS_API_KEY` and `AGENT_API_BASE_URL` environment variable loading
2. Implement `tool_query_api()` function with proper authentication
3. Add `query_api` to TOOL_SCHEMAS
4. Update SYSTEM_PROMPT to guide tool selection
5. Run `uv run run_eval.py` and iterate on failures
6. Add 2 regression tests for system agent tools
7. Update AGENT.md with lessons learned

## Initial Benchmark Strategy

1. Run evaluation: `uv run run_eval.py`
2. For each failure:
   - Check if correct tool was called
   - Check if answer contains expected keywords
   - Adjust system prompt or tool descriptions
3. Re-run until all 10 questions pass

## Known Challenges

- **LLM tool selection**: The LLM might call wrong tool for system questions
- **API path discovery**: LLM needs to know correct API paths
- **Error diagnosis**: Questions 6-7 require reading source code after API error
- **LLM judge questions**: Questions 8-9 need detailed reasoning, not just keywords

## Benchmark Results & Iteration

### Initial Run
- **Score**: 5/10 passed
- **Failures**:
  - Q5 (status code): Agent was sending auth header when it shouldn't
  - Q8-9 (LLM judge): Incomplete answers, agent kept reading more files

### Iteration 1: Added `use_auth` parameter
- Added optional `use_auth` parameter to `query_api` tool
- **Score**: 6/10 passed
- **Remaining failures**: Q8-9 (incomplete synthesis)

### Iteration 2: Updated system prompt for infrastructure questions
- Added explicit file list for infrastructure questions
- **Score**: 8/10 passed
- **Remaining failures**: Q4 (router modules - incomplete answer), Q9 (request journey)

### Iteration 3: Reduced MAX_TOOL_CALLS and added answer detection
- Reduced from 10 to 8 to prevent excessive file reading
- Added detection for "let me continue" patterns
- **Score**: 8/10 passed (inconsistent on Q4)

### Iteration 4: Increased MAX_TOOL_CALLS and improved forced synthesis
- Increased to 12 to allow enough file reads
- Added logic to detect incomplete answers and force synthesis
- **Score**: 10/10 passed ✓

### Final Solution
- **MAX_TOOL_CALLS**: 12
- **Key fix**: Detect when LLM says "let me read more" without tool calls, then force final answer
- **System prompt**: Explicit guidance for each question type
- **Tool schemas**: Clear descriptions with examples

## Final Benchmark Score: 10/10 PASSED ✓
