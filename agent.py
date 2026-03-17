#!/usr/bin/env python3
"""
Agent CLI - An LLM-powered agent with tools for navigating project documentation.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON with 'answer', 'source', and 'tool_calls' fields to stdout.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx


# Maximum number of tool calls per question
MAX_TOOL_CALLS = 10


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


# Tool definitions for LLM function calling
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from the project repository. Use this to read documentation files in the wiki/ directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')"
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
            "description": "List files and directories at a given path in the project repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root (e.g., 'wiki')"
                    }
                },
                "required": ["path"]
            }
        }
    }
]

SYSTEM_PROMPT = """You are a documentation assistant that helps users find information in the project wiki.

You have access to two tools:
1. `list_files` - List files and directories at a given path
2. `read_file` - Read the contents of a file

When answering questions:
1. Use `list_files` to discover what files are available in the wiki/ directory
2. Use `read_file` to read relevant documentation files
3. Always include a source reference in your answer (file path and section anchor if applicable)
4. Call tools iteratively until you have enough information to answer
5. Provide concise, accurate answers based on the documentation you read

Example source format: "wiki/git-workflow.md#resolving-merge-conflicts"
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
    else:
        return f"Error: Unknown tool: {tool_name}"


def extract_source_from_answer(answer: str, tool_calls: list[dict[str, Any]]) -> str:
    """Extract or infer the source reference from the answer and tool calls."""
    # Look for file references in the answer (e.g., wiki/file.md or wiki/file.md#section)
    import re
    
    # Pattern to match wiki file references
    pattern = r"wiki/[\w-]+\.md(?:#[\w-]+)?"
    matches = re.findall(pattern, answer)
    if matches:
        return matches[0]
    
    # If no explicit source in answer, use the last read_file path
    for call in reversed(tool_calls):
        if call.get("tool") == "read_file":
            path = call.get("args", {}).get("path", "")
            if path.startswith("wiki/"):
                return path
    
    return "unknown"


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
        tool_calls = message.get("tool_calls", [])
        
        if not tool_calls:
            # No tool calls - this is the final answer
            answer = message.get("content", "")
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
    # Make one final LLM call to get a summary answer
    messages.append({
        "role": "system",
        "content": "Maximum tool calls reached. Please provide the best answer you can based on the information gathered."
    })
    
    response = asyncio.run(call_llm(
        api_base=api_base,
        api_key=api_key,
        model=model,
        messages=messages,
        tools=None,  # No more tools
    ))
    
    answer = response["choices"][0]["message"].get("content", "")
    source = extract_source_from_answer(answer, all_tool_calls)
    return answer, source, all_tool_calls


def main() -> int:
    """Main entry point."""
    # Check command-line arguments
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py \"<question>\"", file=sys.stderr)
        return 1

    question = sys.argv[1]

    # Load environment variables
    script_dir = Path(__file__).resolve().parent
    env_path = script_dir / ".env.agent.secret"
    env_vars = load_env(env_path)

    # Validate required environment variables
    api_key = env_vars.get("LLM_API_KEY")
    api_base = env_vars.get("LLM_API_BASE")
    model = env_vars.get("LLM_MODEL")

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
    result = {
        "answer": answer,
        "source": source,
        "tool_calls": tool_calls,
    }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
