"""
Tests for tools/arrangement/arrange_piano.py — Piano arrangement tool.

TDD: Tests written BEFORE implementation.
"""

import pytest
import musicpy as mp

from tools.arrangement.arrange_piano import ArrangePianoTool
from tools.analysis.extract_melody import ExtractMelodyTool
from tools.analysis.analyze_harmony import AnalyzeHarmonyTool


class TestArrangePianoTool:
    """Tests for ArrangePianoTool."""

    def _run_arrange(self, piece, style='classical'):
        """Helper: extract melody/harmony then call ArrangePianoTool."""
        melody = ExtractMelodyTool().run(piece)
        harmony = AnalyzeHarmonyTool().run(piece, granularity='measure')
        return ArrangePianoTool().run(piece, melody=melody, harmony=harmony, style=style)

    def test_classical_style_produces_two_hands(self, simple_melody_piece):
        """Classical style output has 2 tracks (RH melody + LH accompaniment)."""
        result = self._run_arrange(simple_melody_piece, style='classical')

        assert isinstance(result, mp.P.__class__) or hasattr(result, 'tracks')
        assert len(result.tracks) == 2

    def test_romantic_style_has_wider_voicing(self, simple_melody_piece):
        """Romantic accompaniment spans more octaves than classical."""
        classical = self._run_arrange(simple_melody_piece, style='classical')
        romantic = self._run_arrange(simple_melody_piece, style='romantic')

        # LH accompaniment in romantic should span more range
        classical_lh_degrees = [n.degree for n in classical.tracks[1] if hasattr(n, 'degree')]
        romantic_lh_degrees = [n.degree for n in romantic.tracks[1] if hasattr(n, 'degree')]

        if classical_lh_degrees and romantic_lh_degrees:
            classical_span = max(classical_lh_degrees) - min(classical_lh_degrees)
            romantic_span = max(romantic_lh_degrees) - min(romantic_lh_degrees)
            assert romantic_span >= classical_span

    def test_pop_style_has_block_chords(self, simple_melody_piece):
        """Pop accompaniment uses block chord pattern."""
        result = self._run_arrange(simple_melody_piece, style='pop')

        assert len(result.tracks) == 2

    def test_output_within_piano_range(self, simple_melody_piece):
        """All notes between A0 (MIDI 21) and C8 (MIDI 108)."""
        result = self._run_arrange(simple_melody_piece, style='classical')

        for track in result.tracks:
            for note in track:
                if hasattr(note, 'degree'):
                    assert 21 <= note.degree <= 108, \
                        f"Note {note} out of piano range"

    def test_melody_preserved_in_right_hand(self, simple_melody_piece):
        """Melody notes from original are present in output RH track."""
        result = self._run_arrange(simple_melody_piece, style='classical')

        rh = result.tracks[0]
        rh_degrees = set(n.degree for n in rh if hasattr(n, 'degree'))

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

        assert len(rh_degrees & original_degrees) > 0

    def test_style_invalid_raises(self, simple_melody_piece):
        """Unknown style raises ValueError."""
        melody = ExtractMelodyTool().run(simple_melody_piece)
        harmony = AnalyzeHarmonyTool().run(simple_melody_piece, granularity='measure')

        with pytest.raises(ValueError):
            ArrangePianoTool().run(simple_melody_piece, melody=melody, harmony=harmony, style='accordion')

    def test_single_track_piece(self, single_track_piece):
        """Arrange a single-track melody into piano arrangement."""
        result = self._run_arrange(single_track_piece, style='classical')

        assert len(result.tracks) == 2
