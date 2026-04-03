"""
Tests for agent/tool_registry.py — Tool registration.

TDD: Tests written BEFORE implementation.
"""

import pytest

from agent.tool_registry import TOOLS, get_tool_names, get_tool_by_name


class TestToolRegistry:
    """Tests for the tool registry."""

    def test_all_tools_registered(self):
        """All expected tools are registered."""
        names = get_tool_names()

        expected = [
            'extract_melody',
            'analyze_harmony',
            'generate_accompaniment',
            'arrange_for_piano',
            'validate_range',
        ]
        for name in expected:
            assert name in names, f"Missing tool: {name}"

    def test_tool_has_name_and_description(self):
        """Each tool has a name and description."""
        for tool in TOOLS:
            assert hasattr(tool, 'name')
            assert hasattr(tool, 'description')
            assert tool.name
            assert tool.description
            assert len(tool.description) > 10

    def test_tool_run_signature(self):
        """Each tool has a run method."""
        for tool in TOOLS:
            assert hasattr(tool, 'run')
            assert callable(tool.run)

    def test_get_tool_by_name(self):
        """Can retrieve a tool by name."""
        tool = get_tool_by_name('arrange_for_piano')
        assert tool is not None
        assert tool.name == 'arrange_for_piano'

    def test_get_unknown_tool_raises(self):
        """Requesting unknown tool raises ValueError."""
        with pytest.raises(ValueError):
            get_tool_by_name('nonexistent_tool')
