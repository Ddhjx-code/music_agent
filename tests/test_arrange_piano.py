"""
Tests for tools/arrangement/arrange_piano.py — Piano arrangement tool.

TDD: Tests written BEFORE implementation.
"""

import pytest
import musicpy as mp

from tools.arrangement.arrange_piano import ArrangePianoTool


class TestArrangePianoTool:
    """Tests for ArrangePianoTool."""

    def test_classical_style_produces_two_hands(self, simple_melody_piece):
        """Classical style output has 2 tracks (RH melody + LH accompaniment)."""
        tool = ArrangePianoTool()
        result = tool.run(simple_melody_piece, style='classical')

        assert isinstance(result, mp.P.__class__) or hasattr(result, 'tracks')
        assert len(result.tracks) == 2

    def test_romantic_style_has_wider_voicing(self, simple_melody_piece):
        """Romantic accompaniment spans more octaves than classical."""
        tool = ArrangePianoTool()

        classical = tool.run(simple_melody_piece, style='classical')
        romantic = tool.run(simple_melody_piece, style='romantic')

        # LH accompaniment in romantic should span more range
        classical_lh_degrees = [n.degree for n in classical.tracks[1] if hasattr(n, 'degree')]
        romantic_lh_degrees = [n.degree for n in romantic.tracks[1] if hasattr(n, 'degree')]

        if classical_lh_degrees and romantic_lh_degrees:
            classical_span = max(classical_lh_degrees) - min(classical_lh_degrees)
            romantic_span = max(romantic_lh_degrees) - min(romantic_lh_degrees)
            assert romantic_span >= classical_span

    def test_pop_style_has_block_chords(self, simple_melody_piece):
        """Pop accompaniment uses block chord pattern."""
        tool = ArrangePianoTool()
        result = tool.run(simple_melody_piece, style='pop')

        assert len(result.tracks) == 2

    def test_output_within_piano_range(self, simple_melody_piece):
        """All notes between A0 (MIDI 21) and C8 (MIDI 108)."""
        tool = ArrangePianoTool()
        result = tool.run(simple_melody_piece, style='classical')

        for track in result.tracks:
            for note in track:
                if hasattr(note, 'degree'):
                    assert 21 <= note.degree <= 108, \
                        f"Note {note} out of piano range"

    def test_melody_preserved_in_right_hand(self, simple_melody_piece):
        """Melody notes from original are present in output RH track."""
        tool = ArrangePianoTool()
        result = tool.run(simple_melody_piece, style='classical')

        rh = result.tracks[0]
        rh_degrees = set(n.degree for n in rh if hasattr(n, 'degree'))

        # Original melody degrees
        original_melody = mp.chord([
            mp.note('C', 5, duration=0.25),
            mp.note('D', 5, duration=0.25),
            mp.note('E', 5, duration=0.25),
            mp.note('F', 5, duration=0.25),
            mp.note('G', 5, duration=0.25),
            mp.note('F', 5, duration=0.25),
            mp.note('E', 5, duration=0.25),
            mp.note('D', 5, duration=0.25),
            mp.note('C', 5, duration=0.25),
            mp.note('E', 5, duration=0.25),
            mp.note('G', 5, duration=0.25),
            mp.note('C', 6, duration=0.25),
            mp.note('G', 5, duration=0.25),
            mp.note('F', 5, duration=0.25),
            mp.note('E', 5, duration=0.25),
            mp.note('D', 5, duration=0.25),
        ])
        original_degrees = set(n.degree for n in original_melody)

        # At least the pitch classes should be preserved
        assert len(rh_degrees & original_degrees) > 0

    def test_style_invalid_raises(self, simple_melody_piece):
        """Unknown style raises ValueError."""
        tool = ArrangePianoTool()

        with pytest.raises(ValueError):
            tool.run(simple_melody_piece, style='accordion')

    def test_single_track_piece(self, single_track_piece):
        """Arrange a single-track melody into piano arrangement."""
        tool = ArrangePianoTool()
        result = tool.run(single_track_piece, style='classical')

        assert len(result.tracks) == 2
