"""Regression tests for agent.py CLI."""

import json
import subprocess
from pathlib import Path


def test_agent_outputs_valid_json_with_required_fields() -> None:
    """Test that agent.py outputs valid JSON with 'answer' and 'tool_calls' fields."""
    # Get the project root directory
    project_root = Path(__file__).resolve().parent.parent
    
    # Run agent.py with a simple question
    result = subprocess.run(
        ["uv", "run", "agent.py", "What does REST stand for?"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=60,
    )
    
    # Check exit code
    assert result.returncode == 0, f"agent.py failed with: {result.stderr}"
    
    # Parse stdout as JSON
    output = json.loads(result.stdout)
    
    # Verify required fields exist
    assert "answer" in output, "Missing 'answer' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"
    
    # Verify field types
    assert isinstance(output["answer"], str), "'answer' should be a string"
    assert isinstance(output["tool_calls"], list), "'tool_calls' should be an array"
    
    # Verify answer is not empty
    assert len(output["answer"].strip()) > 0, "'answer' should not be empty"
