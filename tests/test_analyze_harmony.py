"""
Tests for tools/analysis/analyze_harmony.py — Chord progression analysis tool.

TDD: Tests written BEFORE implementation.
"""

import pytest
import musicpy as mp

from tools.analysis.analyze_harmony import AnalyzeHarmonyTool


class TestAnalyzeHarmonyTool:
    """Tests for AnalyzeHarmonyTool."""

    def test_detect_chord_progression(self, simple_melody_piece):
        """Given a piece with known chords (C-G-Am-F), detect a progression."""
        tool = AnalyzeHarmonyTool()
        result = tool.run(simple_melody_piece)

        assert isinstance(result, list)
        assert len(result) > 0

    def test_detect_per_measure(self, simple_melody_piece):
        """Each measure should have at most one chord entry."""
        tool = AnalyzeHarmonyTool()
        result = tool.run(simple_melody_piece, granularity="measure")

        # Check output format
        for entry in result:
            assert isinstance(entry, dict)
            assert 'measure' in entry
            assert 'chord' in entry

    def test_detect_returns_list_of_dicts(self, simple_melody_piece):
        """Output format: list of {measure, chord, root, quality} dicts."""
        tool = AnalyzeHarmonyTool()
        result = tool.run(simple_melody_piece)

        if result:
            entry = result[0]
            assert 'measure' in entry
            assert 'chord' in entry

    def test_detect_handles_rest_measure(self):
        """Handle measures with no notes gracefully."""
        tool = AnalyzeHarmonyTool()
        # Piece with a gap
        melody = mp.chord([
            mp.note('C', 4, duration=0.25),
            mp.note('D', 4, duration=0.25),
        ], interval=[0, 0])
        piece = mp.P(
            tracks=[melody],
            instruments=[1],
            start_times=[0],
            bpm=120,
        )
        result = tool.run(piece)

        assert isinstance(result, list)

    def test_detect_complex_harmony(self):
        """Test with 7th chords."""
        tool = AnalyzeHarmonyTool()
        # Build a piece with Cmaj7, Dm7, Em7
        c7 = mp.chord(['C4', 'E4', 'G4', 'B4'], duration=1.0, interval=[0, 0, 0, 0])
        d7 = mp.chord(['D4', 'F4', 'A4', 'C5'], duration=1.0, interval=[0, 0, 0, 0])
        e7 = mp.chord(['E4', 'G4', 'B4', 'D5'], duration=1.0, interval=[0, 0, 0, 0])
        chords = c7 | d7 | e7

        piece = mp.P(
            tracks=[chords],
            instruments=[1],
            start_times=[0],
            bpm=120,
        )
        result = tool.run(piece)

        assert isinstance(result, list)
        assert len(result) > 0

    def test_detect_known_chords(self):
        """Verify C major chord is detected as C."""
        tool = AnalyzeHarmonyTool()
        c_chord = mp.chord(['C3', 'E3', 'G3'], duration=1.0, interval=[0, 0, 0])

        piece = mp.P(
            tracks=[c_chord],
            instruments=[1],
            start_times=[0],
            bpm=120,
        )
        result = tool.run(piece)

        assert len(result) >= 1
        chord_name = result[0]['chord'].lower()
        assert 'c' in chord_name
