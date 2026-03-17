# Task 1: Call an LLM from Code

## Overview
Build a Python CLI program (`agent.py`) that takes a question as a command-line argument, sends it to an LLM via an OpenAI-compatible API, and returns a structured JSON response.

## LLM Provider and Model

### Provider: Qwen Code API (via local proxy)
- **Base URL**: `http://10.93.25.111:42005/v1`
- **Model**: `qwen3-coder-plus`
- **Authentication**: API key stored in `.env.agent.secret`

### Why this provider?
- Works from Russia without restrictions
- Provides 1000 free requests per day
- No credit card required
- OpenAI-compatible chat completions API
- Strong reasoning capabilities with qwen3-coder-plus model

## Architecture

### Input/Output Flow
```
CLI Argument → agent.py → LLM API → JSON Response → stdout
```

### Components

1. **Environment Loading**
   - Read `.env.agent.secret` for `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`
   - Use `python-dotenv` or manual parsing

2. **LLM Client**
   - Use `httpx` (already in dependencies) for async HTTP requests
   - Call OpenAI-compatible chat completions endpoint: `POST /chat/completions`
   - Request body: `{"model": "...", "messages": [{"role": "user", "content": "..."}]}`
   - Headers: `Authorization: Bearer <API_KEY>`, `Content-Type: application/json`

3. **Response Parsing**
   - Extract `choices[0].message.content` from LLM response
   - Format as JSON: `{"answer": "<content>", "tool_calls": []}`

4. **Output**
   - Valid JSON to stdout (single line)
   - Debug/progress info to stderr
   - Exit code 0 on success, non-zero on error
   - 60-second timeout for API call

## Implementation Steps

1. Create `.env.agent.secret` from `.env.agent.example` with filled credentials
2. Implement `agent.py`:
   - Parse command-line argument (question)
   - Load environment variables
   - Make async HTTP request to LLM
   - Parse response and output JSON
3. Create `AGENT.md` documentation
4. Write regression test in `backend/tests/unit/test_agent.py`

## Error Handling
- Missing command-line argument → print usage to stderr, exit 1
- Missing environment variables → print error to stderr, exit 1
- API timeout (>60s) → print error to stderr, exit 1
- API error → print error to stderr, exit 1
- Invalid JSON response → print error to stderr, exit 1

## Testing
- Unit test that runs `agent.py` as subprocess
- Verify stdout is valid JSON with `answer` and `tool_calls` fields
- Test with a simple question like "What does REST stand for?"
