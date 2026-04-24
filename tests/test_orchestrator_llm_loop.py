"""Tests for the new LLM loop orchestrator.

Tests the deprecated create_music_agent wrapper to verify it still
produces a valid output piece when called, even though the internal
implementation has changed from a flat LLM loop to RoleOrchestrator.
"""

import json
import warnings
import pytest
from unittest.mock import MagicMock

from core.orchestrator import create_music_agent


class TestLLMLoopOrchestrator:
    """Test that the deprecated create_music_agent still works."""

    def test_llm_receives_json_and_chooses_action(self, simple_melody_piece):
        """Deprecation shim: agent runs RoleOrchestrator and returns a result."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _mock_response({
            'passed': True, 'issues': [], 'done': True,
            'phases': ['arrangement'], 'params': {'style': 'romantic'},
            'actions': [], 'tracks_before': 2, 'tracks_after': 2,
        })

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            agent = create_music_agent(mock_llm)
        result_piece = agent(simple_melody_piece, "Make this a romantic piano piece")

        assert isinstance(result_piece, list)

    def test_llm_can_chain_multiple_actions(self, simple_melody_piece):
        """Deprecation shim: multiple phases."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _mock_response({
            'passed': True, 'issues': [], 'done': True,
            'phases': ['arrangement', 'expression'], 'params': {'style': 'classical'},
            'actions': [], 'tracks_before': 2, 'tracks_after': 2,
        })

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            agent = create_music_agent(mock_llm)
        result_piece = agent(simple_melody_piece, "Analyze and arrange as piano")

        assert isinstance(result_piece, list)

    def test_llm_sees_music_json_in_prompt(self, simple_melody_piece):
        """The prompt sent to LLM should include music context."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _mock_response({
            'passed': True, 'issues': [], 'done': True,
            'phases': ['arrangement'], 'params': {},
            'actions': [], 'tracks_before': 2, 'tracks_after': 2,
        })

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            agent = create_music_agent(mock_llm)
        agent(simple_melody_piece, "Test")

        # Verify LLM was invoked with music context
        assert mock_llm.invoke.call_count >= 1
        # Check at least one call contained track/summary info
        found_context = False
        for call in mock_llm.invoke.call_args_list:
            if call.args:
                messages = call.args[0]
                if hasattr(messages, '__iter__') and not isinstance(messages, str):
                    content = ' '.join(str(getattr(m, 'content', '')) for m in messages if hasattr(m, 'content'))
                    if 'track' in content.lower() or 'summary' in content.lower() or 'analyst' in content.lower():
                        found_context = True
                        break
        assert found_context, "LLM prompt should include music context"

    def test_fallback_on_json_parse_error(self, simple_melody_piece):
        """If LLM returns invalid JSON for Planner, should gracefully handle it."""
        bad_resp = MagicMock(content="Sure, I'll arrange this as piano! Here's what I think...")
        good_resp = _mock_response({
            'passed': True, 'issues': [], 'done': True,
            'phases': ['arrangement'], 'params': {},
            'actions': [], 'tracks_before': 2, 'tracks_after': 2,
        })
        mock_llm = MagicMock()
        # First call gets bad JSON, subsequent calls return good response
        mock_llm.invoke.side_effect = [bad_resp, good_resp, good_resp, good_resp, good_resp]

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            agent = create_music_agent(mock_llm)
        result_piece = agent(simple_melody_piece, "Arrange as piano")
        assert isinstance(result_piece, list)


def _mock_response(data):
    """Create a mock LLM response with JSON content."""
    resp = MagicMock()
    resp.content = json.dumps(data)
    return resp
