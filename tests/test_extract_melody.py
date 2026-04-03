"""
Tests for tools/analysis/extract_melody.py — Melody extraction tool.

TDD: Tests written BEFORE implementation.
"""

import pytest
import musicpy as mp

from tools.analysis.extract_melody import ExtractMelodyTool


class TestExtractMelodyTool:
    """Tests for ExtractMelodyTool."""

    def test_extract_from_single_melody_track(self, single_track_piece):
        """Given a single-track MIDI, return the same track."""
        tool = ExtractMelodyTool()
        result = tool.run(single_track_piece)

        assert isinstance(result, mp.chord)
        assert len(result) == len(single_track_piece.tracks[0])

    def test_extract_from_multi_track(self, simple_melody_piece):
        """Given 2 tracks (melody + chords), return only melody."""
        tool = ExtractMelodyTool()
        result = tool.run(simple_melody_piece)

        assert isinstance(result, mp.chord)
        # Melody has 16 notes, chord track has 12 notes (3 notes x 4 chords)
        # The melody track should be selected (higher average pitch)
        assert len(result) == 16

    def test_extract_highest_voice(self, pop_song_piece):
        """Melody should be the highest-pitched track."""
        tool = ExtractMelodyTool()
        result = tool.run(pop_song_piece)

        # Vocal track has the highest average pitch (G4-D5 range)
        degrees = [n.degree for n in result if hasattr(n, 'degree')]
        assert max(degrees) >= 62  # D5 = MIDI 62

    def test_extract_returns_chord_object(self, simple_melody_piece):
        """Return type is musicpy chord."""
        tool = ExtractMelodyTool()
        result = tool.run(simple_melody_piece)

        assert isinstance(result, mp.chord)

    def test_extract_with_confidence_threshold(self, simple_melody_piece):
        """Lower confidence threshold includes more notes."""
        tool = ExtractMelodyTool()

        strict = tool.run(simple_melody_piece, confidence=0.9)
        relaxed = tool.run(simple_melody_piece, confidence=0.3)

        # Relaxed should include at least as many notes as strict
        assert len(relaxed) >= len(strict)

    def test_extract_empty_piece(self):
        """Handle an empty piece gracefully."""
        tool = ExtractMelodyTool()
        empty_piece = mp.P(
            tracks=[mp.chord([])],
            instruments=[1],
            start_times=[0],
            bpm=120,
        )
        result = tool.run(empty_piece)

        assert isinstance(result, mp.chord)
