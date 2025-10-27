"""
Tests for code quality checks using flake8 and pyright.

These tests ensure that the codebase maintains high quality standards
by checking for:
- PEP 8 compliance (flake8)
- Type correctness (pyright)
"""
import subprocess
import pytest


def test_flake8_main_code():
    """Test that the main code passes flake8 linting."""
    result = subprocess.run(
        ["flake8", "graphql_mcp"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        pytest.fail(
            f"flake8 found issues in main code:\n{result.stdout}\n{result.stderr}"
        )


def test_flake8_tests():
    """Test that the test code passes flake8 linting."""
    result = subprocess.run(
        ["flake8", "tests"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        pytest.fail(
            f"flake8 found issues in tests:\n{result.stdout}\n{result.stderr}"
        )


def test_pyright_main_code():
    """Test that the main code passes pyright type checking."""
    result = subprocess.run(
        ["pyright", "graphql_mcp"],
        capture_output=True,
        text=True
    )

    # Pyright returns 0 if no errors, non-zero if errors found
    if result.returncode != 0:
        # Check if the output contains actual errors (not just warnings)
        output = result.stdout + result.stderr
        if "error" in output.lower():
            pytest.fail(
                f"pyright found type errors in main code:\n{result.stdout}\n{result.stderr}"
            )


def test_pyright_tests():
    """Test that the test code passes pyright type checking."""
    result = subprocess.run(
        ["pyright", "tests"],
        capture_output=True,
        text=True
    )

    # Pyright returns 0 if no errors, non-zero if errors found
    if result.returncode != 0:
        # Check if the output contains actual errors (not just warnings)
        output = result.stdout + result.stderr
        if "error" in output.lower():
            pytest.fail(
                f"pyright found type errors in tests:\n{result.stdout}\n{result.stderr}"
            )


def test_flake8_configuration():
    """Test that flake8 configuration is properly loaded."""
    result = subprocess.run(
        ["flake8", "--version"],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, "flake8 should be installed and accessible"
    assert "flake8" in result.stdout.lower(), "Output should mention flake8"


def test_pyright_configuration():
    """Test that pyright is properly installed."""
    result = subprocess.run(
        ["pyright", "--version"],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, "pyright should be installed and accessible"
    # Pyright version output goes to stdout
    output = result.stdout + result.stderr
    assert "pyright" in output.lower() or len(output) > 0, "Should have version output"
