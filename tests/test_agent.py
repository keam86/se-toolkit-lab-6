"""Regression tests for agent.py CLI with tool calling."""

import json
import subprocess
from pathlib import Path


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).resolve().parent.parent


def run_agent(question: str) -> tuple[int, dict, str]:
    """Run agent.py with a question and return (exit_code, output_json, stderr)."""
    project_root = get_project_root()
    result = subprocess.run(
        ["uv", "run", "agent.py", question],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=120,
    )
    output = json.loads(result.stdout) if result.stdout else {}
    return result.returncode, output, result.stderr


def test_agent_merge_conflict_question_uses_read_file() -> None:
    """Test that agent uses read_file tool for merge conflict question."""
    returncode, output, stderr = run_agent("How do you resolve a merge conflict?")
    
    # Check exit code
    assert returncode == 0, f"agent.py failed with: {stderr}"
    
    # Verify required fields exist
    assert "answer" in output, "Missing 'answer' field in output"
    assert "source" in output, "Missing 'source' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"
    
    # Verify tool_calls is populated
    tool_calls = output["tool_calls"]
    assert isinstance(tool_calls, list), "'tool_calls' should be an array"
    assert len(tool_calls) > 0, "Expected at least one tool call"
    
    # Verify read_file was used
    tool_names = [call.get("tool") for call in tool_calls]
    assert "read_file" in tool_names, "Expected 'read_file' tool to be called"
    
    # Verify source contains wiki file reference
    source = output["source"]
    assert isinstance(source, str), "'source' should be a string"
    assert "wiki/" in source, f"Source should reference wiki/, got: {source}"
    
    # Verify answer is not empty
    assert len(output["answer"].strip()) > 0, "'answer' should not be empty"


def test_agent_wiki_files_question_uses_list_files() -> None:
    """Test that agent uses list_files tool for wiki files question."""
    returncode, output, stderr = run_agent("What files are in the wiki?")
    
    # Check exit code
    assert returncode == 0, f"agent.py failed with: {stderr}"
    
    # Verify required fields exist
    assert "answer" in output, "Missing 'answer' field in output"
    assert "source" in output, "Missing 'source' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"
    
    # Verify tool_calls is populated
    tool_calls = output["tool_calls"]
    assert isinstance(tool_calls, list), "'tool_calls' should be an array"
    assert len(tool_calls) > 0, "Expected at least one tool call"
    
    # Verify list_files was used
    tool_names = [call.get("tool") for call in tool_calls]
    assert "list_files" in tool_names, "Expected 'list_files' tool to be called"
    
    # Verify answer is not empty
    assert len(output["answer"].strip()) > 0, "'answer' should not be empty"
