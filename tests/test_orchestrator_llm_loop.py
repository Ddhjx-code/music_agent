"""Tests for the new LLM loop orchestrator."""

import json
import pytest
from unittest.mock import MagicMock

from core.orchestrator import create_music_agent


class TestLLMLoopOrchestrator:
    """Test that LLM participates in a loop with JSON feedback."""

    def test_llm_receives_json_and_chooses_action(self, simple_melody_piece):
        """LLM should receive JSON and choose actions."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            _mock_response({'action': 'arrange_for_piano', 'style': 'romantic', 'done': False}),
            _mock_response({'done': True}),
        ]

        agent = create_music_agent(mock_llm)
        results = agent(simple_melody_piece, "Make this a romantic piano piece")

        actions = [cmd.get('action') for cmd, _ in results]
        assert 'arrange_for_piano' in actions

    def test_llm_can_chain_multiple_actions(self, simple_melody_piece):
        """LLM should be able to chain: analyze → arrange → validate."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            _mock_response({'action': 'analyze_harmony', 'done': False}),
            _mock_response({'action': 'arrange_for_piano', 'style': 'classical', 'done': False}),
            _mock_response({'action': 'validate_range', 'instrument': 'piano', 'done': False}),
            _mock_response({'done': True}),
        ]

        agent = create_music_agent(mock_llm)
        results = agent(simple_melody_piece, "Analyze and arrange as piano")

        actions = [cmd.get('action') for cmd, _ in results]
        assert 'analyze_harmony' in actions
        assert 'arrange_for_piano' in actions
        assert 'validate_range' in actions

    def test_llm_sees_music_json_in_prompt(self, simple_melody_piece):
        """The prompt sent to LLM should include the music JSON."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            _mock_response({'done': True}),
        ]

        agent = create_music_agent(mock_llm)
        agent(simple_melody_piece, "Test")

        call_args = mock_llm.invoke.call_args[0][0]
        human_msg = str(call_args[-1].content)
        assert 'summary' in human_msg or 'tracks' in human_msg

    def test_fallback_on_json_parse_error(self, simple_melody_piece):
        """If LLM returns invalid JSON, should gracefully handle it."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            MagicMock(content="Sure, I'll arrange this as piano! Here's what I think..."),
            _mock_response({'done': True}),
        ]

        agent = create_music_agent(mock_llm)
        results = agent(simple_melody_piece, "Arrange as piano")
        assert isinstance(results, list)


def _mock_response(data):
    """Create a mock LLM response with JSON content."""
    resp = MagicMock()
    resp.content = json.dumps(data)
    return resp
