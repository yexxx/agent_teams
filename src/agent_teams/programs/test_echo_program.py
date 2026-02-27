"""Tests for the echo program."""

import subprocess
import sys


def test_echo_program_default_message() -> None:
    """Test that echo program outputs default message when no arguments provided."""
    result = subprocess.run(
        [sys.executable, "echo_program.py"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "Hello, World!" in result.stdout


def test_echo_program_custom_message() -> None:
    """Test that echo program outputs custom message when arguments provided."""
    result = subprocess.run(
        [sys.executable, "echo_program.py", "Custom", "message", "here"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "Custom message here" in result.stdout


def test_echo_program_single_argument() -> None:
    """Test that echo program works with single argument."""
    result = subprocess.run(
        [sys.executable, "echo_program.py", "Test"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "Test" in result.stdout


if __name__ == "__main__":
    # Run tests when script is executed directly
    test_echo_program_default_message()
    test_echo_program_custom_message()
    test_echo_program_single_argument()
    print("All tests passed!")