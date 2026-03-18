#!/usr/bin/env python3
"""
Agent CLI - An LLM-powered agent with tools for navigating project documentation
and querying the deployed backend API.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON with 'answer', 'source' (optional), and 'tool_calls' fields to stdout.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx


# Maximum number of tool calls per question
MAX_TOOL_CALLS = 12


def load_env(env_path: Path) -> dict[str, str]:
    """Load environment variables from a .env file."""
    env_vars = {}
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars


def validate_path(requested_path: str, project_root: Path) -> tuple[bool, str | Path]:
    """
    Validate that a path is within the project directory.
    
    Returns:
        (is_valid, result) - if valid, result is the absolute Path; otherwise error message
    """
    # Reject absolute paths or path traversal
    if requested_path.startswith("/") or ".." in requested_path:
        return False, "Error: Path traversal not allowed"
    
    # Resolve the full path
    full_path = (project_root / requested_path).resolve()
    
    # Ensure it's within project root
    try:
        full_path.relative_to(project_root.resolve())
        return True, full_path
    except ValueError:
        return False, "Error: Path must be within project directory"


def tool_read_file(path: str, project_root: Path) -> str:
    """Read a file from the project repository."""
    is_valid, result = validate_path(path, project_root)
    if not is_valid:
        return str(result)
    
    full_path = Path(result)
    
    if not full_path.exists():
        return f"Error: File not found: {path}"
    
    if not full_path.is_file():
        return f"Error: Not a file: {path}"
    
    try:
        with open(full_path, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error: Could not read file: {e}"


def tool_list_files(path: str, project_root: Path) -> str:
    """List files and directories at a given path."""
    is_valid, result = validate_path(path, project_root)
    if not is_valid:
        return str(result)
    
    full_path = Path(result)
    
    if not full_path.exists():
        return f"Error: Directory not found: {path}"
    
    if not full_path.is_dir():
        return f"Error: Not a directory: {path}"
    
    try:
        entries = sorted(full_path.iterdir())
        lines = [e.name for e in entries]
        return "\n".join(lines)
    except Exception as e:
        return f"Error: Could not list directory: {e}"


def tool_query_api(method: str, path: str, body: str | None = None, use_auth: bool = True) -> str:
    """
    Call the deployed backend API with optional authentication.
    
    Args:
        method: HTTP method (GET, POST, PUT, DELETE, PATCH)
        path: API path (e.g., '/items/', '/analytics/completion-rate')
        body: Optional JSON request body for POST/PUT/PATCH requests
        use_auth: Whether to include authentication header (default True)
    
    Returns:
        JSON string with status_code and body, or error message
    """
    api_base = os.environ.get("AGENT_API_BASE_URL", "http://localhost:42002")
    api_key = os.environ.get("LMS_API_KEY")
    
    url = f"{api_base}{path}"
    headers = {
        "Content-Type": "application/json",
    }
    
    if use_auth:
        if not api_key:
            return json.dumps({"error": "LMS_API_KEY not set in environment"})
        headers["Authorization"] = f"Bearer {api_key}"
    
    try:
        with httpx.Client(timeout=30.0) as client:
            if method.upper() == "GET":
                response = client.get(url, headers=headers)
            elif method.upper() == "POST":
                data = json.loads(body) if body else {}
                response = client.post(url, headers=headers, json=data)
            elif method.upper() == "PUT":
                data = json.loads(body) if body else {}
                response = client.put(url, headers=headers, json=data)
            elif method.upper() == "DELETE":
                response = client.delete(url, headers=headers)
            elif method.upper() == "PATCH":
                data = json.loads(body) if body else {}
                response = client.patch(url, headers=headers, json=data)
            else:
                return json.dumps({"error": f"Unsupported method: {method}"})
            
            result = {
                "status_code": response.status_code,
                "body": response.text,
            }
            return json.dumps(result)
    except httpx.TimeoutException:
        return json.dumps({"error": "Request timed out"})
    except httpx.RequestError as e:
        return json.dumps({"error": f"Request failed: {str(e)}"})
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON body: {str(e)}"})
    except Exception as e:
        return json.dumps({"error": f"Unexpected error: {str(e)}"})


# Tool definitions for LLM function calling
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from the project repository. Use this to read documentation files in the wiki/ directory or source code files to understand the system architecture.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root (e.g., 'wiki/git-workflow.md' or 'backend/app/routers/items.py')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path in the project repository. Use this to discover what files exist in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root (e.g., 'wiki' or 'backend/app/routers')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Call the deployed backend API to query data or check system behavior. Use this for questions about database contents, API responses, status codes, or current system state. Set use_auth=false to test unauthenticated access.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "description": "HTTP method (GET, POST, PUT, DELETE, PATCH)",
                        "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]
                    },
                    "path": {
                        "type": "string",
                        "description": "API path (e.g., '/items/', '/analytics/completion-rate', '/analytics/top-learners')"
                    },
                    "body": {
                        "type": "string",
                        "description": "Optional JSON request body for POST/PUT/PATCH requests"
                    },
                    "use_auth": {
                        "type": "boolean",
                        "description": "Whether to include authentication header. Set to false to test unauthenticated access (default: true)"
                    }
                },
                "required": ["method", "path"]
            }
        }
    }
]

SYSTEM_PROMPT = """You are a documentation and system assistant that helps users find information about the project.

You have access to three tools:
1. `list_files` - List files and directories at a given path
2. `read_file` - Read the contents of a file
3. `query_api` - Call the deployed backend API to query data or check system behavior

When answering questions:

**For wiki/documentation questions** (e.g., "According to the wiki...", "What does the documentation say..."):
- Use `list_files` to discover what files are available in the wiki/ directory
- Use `read_file` to read relevant documentation files
- Include source references (file path and section anchor)

**For source code questions** (e.g., "What framework does the backend use?", "Show me the routers"):
- Use `list_files` to explore the backend/ directory structure
- Use `read_file` to read source code files
- **Key files to know about:**
  - `backend/app/etl.py` - ETL pipeline for fetching data from autochecker API
  - `backend/app/run.py` - Main FastAPI application entry point
  - `backend/app/routers/` - API routers (items.py, learners.py, interactions.py, analytics.py, pipeline.py)
- After gathering information, provide a complete summary answer

**For system/data questions** (e.g., "How many items...", "What status code...", "Query the API..."):
- Use `query_api` to query the running backend
- Common endpoints:
  - `/items/` - List all items
  - `/learners/` - List all learners (count for distinct learners questions)
  - `/interactions/` - List all interactions
  - `/analytics/completion-rate` - Get completion rate
  - `/analytics/top-learners` - Get top learners
- For counting questions: Query the appropriate list endpoint and count the results
- Include the actual data from the API response

**For infrastructure/deployment questions** (e.g., "request journey", "docker-compose", "Dockerfile", "how requests flow"):
- Read these specific files in order: `docker-compose.yml`, `backend/Dockerfile`, `caddy/Caddyfile`, `backend/app/run.py`
- After reading these 4 files, synthesize the complete request flow
- Do not read additional files beyond these unless absolutely necessary
- Trace the complete flow: browser → Caddy reverse proxy → FastAPI app → PostgreSQL database → back

**For error diagnosis questions** (e.g., "What bug...", "Why does it crash...", "Which endpoint is risky..."):
- First use `query_api` to reproduce the error if applicable
- Then use `read_file` to examine the source code
- **When looking for bugs, specifically check for:**
  - Division operations that could cause ZeroDivisionError (look for `/` operator)
  - Sorting operations with potentially None values (look for `sorted()`, `.sort()`)
  - None-unsafe operations (accessing attributes/methods on potentially None values)
  - Missing error handling for edge cases
- Identify the exact line and explain the root cause

**For ETL pipeline questions** (e.g., "idempotency", "ETL", "pipeline", "how data is loaded"):
- Read `backend/app/etl.py` - this is the ETL pipeline code
- Look for:
  - `external_id` checks to prevent duplicate records
  - Transaction handling with `session.commit()` and rollback behavior
  - How the pipeline handles re-running with the same data

**For comparison questions** (e.g., "Compare X and Y...", "How does A differ from B..."):
- Read the source code for both components being compared
- For error handling comparisons specifically:
  - Look for try/except blocks in each component
  - Check how errors are logged, re-raised, or silently handled
  - Identify if one uses transactions/rollbacks vs the other doesn't
  - Note differences in exception types caught
- Identify key differences in approach, patterns, or behavior
- Provide a structured comparison highlighting similarities and differences

Important: After gathering information with tools, always provide a complete, final answer that directly addresses the user's question. When you have read the relevant files, synthesize the information into a comprehensive answer. Do not say "let me continue" or similar phrases in your final response - instead, provide the complete answer based on what you have learned.
"""


async def call_llm(
    api_base: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Call the LLM API and return the response."""
    url = f"{api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


def execute_tool(tool_name: str, args: dict[str, Any], project_root: Path) -> str:
    """Execute a tool and return the result."""
    if tool_name == "read_file":
        path = args.get("path", "")
        return tool_read_file(path, project_root)
    elif tool_name == "list_files":
        path = args.get("path", "")
        return tool_list_files(path, project_root)
    elif tool_name == "query_api":
        method = args.get("method", "GET")
        path = args.get("path", "")
        body = args.get("body")
        use_auth = args.get("use_auth", True)
        return tool_query_api(method, path, body, use_auth)
    else:
        return f"Error: Unknown tool: {tool_name}"


def extract_source_from_answer(answer: str, tool_calls: list[dict[str, Any]]) -> str:
    """Extract or infer the source reference from the answer and tool calls."""
    import re
    
    # Look for wiki file references in the answer
    pattern = r"wiki/[\w-]+\.md(?:#[\w-]+)?"
    matches = re.findall(pattern, answer)
    if matches:
        return matches[0]
    
    # Look for backend file references
    pattern = r"backend/[\w/.-]+\.py"
    matches = re.findall(pattern, answer)
    if matches:
        return matches[0]
    
    # If no explicit source in answer, use the last read_file path
    for call in reversed(tool_calls):
        if call.get("tool") == "read_file":
            path = call.get("args", {}).get("path", "")
            if path.startswith("wiki/") or path.startswith("backend/"):
                return path
    
    return ""


def run_agentic_loop(
    api_base: str,
    api_key: str,
    model: str,
    question: str,
    project_root: Path,
) -> tuple[str, str, list[dict[str, Any]]]:
    """
    Run the agentic loop: call LLM, execute tools, repeat until answer.
    
    Returns:
        (answer, source, tool_calls)
    """
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    
    all_tool_calls: list[dict[str, Any]] = []
    
    for iteration in range(MAX_TOOL_CALLS + 1):
        # Call LLM
        response = asyncio.run(call_llm(
            api_base=api_base,
            api_key=api_key,
            model=model,
            messages=messages,
            tools=TOOL_SCHEMAS,
        ))
        
        choice = response["choices"][0]
        message = choice["message"]

        # Check for tool calls
        tool_calls = message.get("tool_calls") or []
        content = message.get("content") or ""

        if not tool_calls:
            # No tool calls - check if this is a real answer or just saying "let me continue"
            if content and any(phrase in content.lower() for phrase in ["let me", "i'll", "i will", "now i", "next", "continue", "need to read", "should check"]):
                # LLM is saying it wants to continue but has no tool calls
                # Force a final answer by calling LLM without tools
                messages.append({"role": "system", "content": "Provide a complete answer based on the information you have already gathered. Do not say you need to read more files."})
                response = asyncio.run(call_llm(
                    api_base=api_base,
                    api_key=api_key,
                    model=model,
                    messages=messages,
                    tools=None,
                ))
                answer = response["choices"][0]["message"].get("content") or ""
                source = extract_source_from_answer(answer, all_tool_calls)
                return answer, source, all_tool_calls
            
            # No tool calls - this is the final answer
            answer = content
            source = extract_source_from_answer(answer, all_tool_calls)
            return answer, source, all_tool_calls

        # Check if the LLM is providing a final answer along with tool calls
        # If content looks like a complete answer, use it
        if content and not any(phrase in content.lower() for phrase in ["let me", "i'll", "i will", "now i", "next", "continue"]):
            # LLM provided content that looks like an answer
            # Check if it's substantial (more than 100 chars and doesn't end with colon)
            if len(content) > 100 and not content.strip().endswith(":"):
                answer = content
                source = extract_source_from_answer(answer, all_tool_calls)
                return answer, source, all_tool_calls

        # Execute tool calls
        messages.append(message)
        
        for tool_call in tool_calls:
            tool_id = tool_call["id"]
            tool_name = tool_call["function"]["name"]
            tool_args = json.loads(tool_call["function"]["arguments"])
            
            # Execute the tool
            result = execute_tool(tool_name, tool_args, project_root)
            
            # Record the tool call
            all_tool_calls.append({
                "tool": tool_name,
                "args": tool_args,
                "result": result,
            })
            
            # Add tool result to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tool_id,
                "content": result,
            })
    
    # Max iterations reached - use whatever answer we have
    messages.append({
        "role": "system",
        "content": "You have gathered enough information. Now provide a complete, comprehensive answer that directly addresses the user's question. Synthesize all the information you have collected from the files and tools. Do not say you need to read more files - instead, provide the final answer based on what you have learned."
    })
    
    response = asyncio.run(call_llm(
        api_base=api_base,
        api_key=api_key,
        model=model,
        messages=messages,
        tools=None,
    ))
    
    answer = response["choices"][0]["message"].get("content") or ""
    source = extract_source_from_answer(answer, all_tool_calls)
    return answer, source, all_tool_calls


def main() -> int:
    """Main entry point."""
    # Check command-line arguments
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py \"<question>\"", file=sys.stderr)
        return 1

    question = sys.argv[1]

    # Load LLM environment variables from .env.agent.secret
    script_dir = Path(__file__).resolve().parent
    env_path = script_dir / ".env.agent.secret"
    env_vars = load_env(env_path)

    # LLM config: prefer env vars from file, but allow override from environment
    api_key = os.environ.get("LLM_API_KEY") or env_vars.get("LLM_API_KEY")
    api_base = os.environ.get("LLM_API_BASE") or env_vars.get("LLM_API_BASE")
    model = os.environ.get("LLM_MODEL") or env_vars.get("LLM_MODEL")
    
    # LMS API config: read from environment (autochecker injects these)
    # Also try loading from .env.docker.secret for local development
    docker_env_path = script_dir / ".env.docker.secret"
    docker_env_vars = load_env(docker_env_path)
    lms_api_key = os.environ.get("LMS_API_KEY") or docker_env_vars.get("LMS_API_KEY")
    agent_api_base_url = os.environ.get("AGENT_API_BASE_URL", "http://localhost:42002")
    
    # Set LMS_API_KEY in environment for tool_query_api to use
    if lms_api_key:
        os.environ["LMS_API_KEY"] = lms_api_key
    if not os.environ.get("AGENT_API_BASE_URL"):
        os.environ["AGENT_API_BASE_URL"] = agent_api_base_url

    if not api_key:
        print("Error: LLM_API_KEY not set in .env.agent.secret", file=sys.stderr)
        return 1
    if not api_base:
        print("Error: LLM_API_BASE not set in .env.agent.secret", file=sys.stderr)
        return 1
    if not model:
        print("Error: LLM_MODEL not set in .env.agent.secret", file=sys.stderr)
        return 1

    # Get project root
    project_root = script_dir

    # Run agentic loop
    try:
        answer, source, tool_calls = run_agentic_loop(
            api_base=api_base,
            api_key=api_key,
            model=model,
            question=question,
            project_root=project_root,
        )
    except httpx.TimeoutException:
        print("Error: LLM request timed out after 60 seconds", file=sys.stderr)
        return 1
    except httpx.HTTPStatusError as e:
        print(f"Error: LLM API returned error status: {e.response.status_code}", file=sys.stderr)
        return 1
    except httpx.RequestError as e:
        print(f"Error: Failed to connect to LLM API: {e}", file=sys.stderr)
        return 1
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"Error: Failed to parse LLM response: {e}", file=sys.stderr)
        return 1

    # Output result as JSON
    result: dict[str, Any] = {
        "answer": answer,
        "tool_calls": tool_calls,
    }
    if source:
        result["source"] = source
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
