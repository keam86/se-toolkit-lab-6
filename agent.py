#!/usr/bin/env python3
"""
Agent CLI - A simple LLM-powered question answering CLI.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON with 'answer' and 'tool_calls' fields to stdout.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx


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


async def call_llm(
    api_base: str, api_key: str, model: str, question: str, timeout: float = 60.0
) -> str:
    """Call the LLM API and return the answer."""
    url = f"{api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant. Provide concise, accurate answers."},
            {"role": "user", "content": question},
        ],
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


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

    # Call the LLM
    try:
        answer = asyncio.run(call_llm(api_base, api_key, model, question))
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
        "tool_calls": [],
    }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
