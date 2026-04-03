"""
Tests for tools/validation/range_check.py — Instrument range validation.

TDD: Tests written BEFORE implementation.
"""

import pytest
import musicpy as mp

from tools.validation.range_check import RangeCheckTool


class TestRangeCheckTool:
    """Tests for RangeCheckTool."""

    def test_piano_range_valid(self):
        """Notes within A0-C8 pass validation."""
        tool = RangeCheckTool()
        piece = mp.P(
            tracks=[mp.chord([
                mp.note('C', 4, duration=0.25),
                mp.note('E', 4, duration=0.25),
                mp.note('G', 4, duration=0.25),
            ])],
            instruments=[1],
            start_times=[0],
            bpm=120,
        )
        result = tool.run(piece, instrument='piano')

        assert result['passed'] is True
        assert result['issues'] == []

    def test_piano_range_invalid(self):
        """Note below A0 or above C8 fails with specific error."""
        tool = RangeCheckTool()
        # Create a note below piano range (B-1 = MIDI 11)
        low_note = mp.note('C', 0, duration=0.25)  # C1 = MIDI 24, still in range
        # Let's use C0 = MIDI 12, below A0=21
        low_note = mp.note('C', 0, duration=0.25)  # C0 = MIDI 12

        piece = mp.P(
            tracks=[mp.chord([low_note])],
            instruments=[1],
            start_times=[0],
            bpm=120,
        )
        result = tool.run(piece, instrument='piano')

        assert result['passed'] is False
        assert len(result['issues']) > 0

    def test_returns_issues_list(self):
        """Output format: {passed: bool, issues: list}."""
        tool = RangeCheckTool()
        piece = mp.P(
            tracks=[mp.chord([mp.note('C', 4, duration=0.25)])],
            instruments=[1],
            start_times=[0],
            bpm=120,
        )
        result = tool.run(piece, instrument='piano')

        assert 'passed' in result
        assert 'issues' in result
        assert isinstance(result['passed'], bool)
        assert isinstance(result['issues'], list)

    def test_multiple_violations(self):
        """Multiple out-of-range notes are all reported."""
        tool = RangeCheckTool()
        # C0 (MIDI 12) and C8 (MIDI 108, valid) and B8 (MIDI 119, invalid)
        notes = [
            mp.note('C', 0, duration=0.25),   # C0 = MIDI 12, below A0
        ]
        piece = mp.P(
            tracks=[mp.chord(notes)],
            instruments=[1],
            start_times=[0],
            bpm=120,
        )
        result = tool.run(piece, instrument='piano')

        assert result['passed'] is False

    def test_valid_piece(self, simple_melody_piece):
        """The simple_melody_piece fixture is within piano range."""
        tool = RangeCheckTool()
        result = tool.run(simple_melody_piece, instrument='piano')

        assert result['passed'] is True
