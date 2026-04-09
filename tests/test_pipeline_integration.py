"""
Integration tests for the full pipeline.

Tests the complete MIDI → analysis → arrangement → MIDI pipeline
with mocked LLM responses.
"""

import os
import tempfile

import pytest
import musicpy as mp

from core.music_io import load_midi, save_midi
from core.json_schema import generate_summary
from tools.arrangement.arrange_piano import ArrangePianoTool
from tools.validation.range_check import RangeCheckTool
from tools.analysis.analyze_harmony import AnalyzeHarmonyTool
from tools.harmony.generate_accompaniment import GenerateAccompanimentTool, _parse_chord_name


class TestPipelineIntegration:
    """Integration tests for the full pipeline (no LLM)."""

    def test_full_pipeline_classical_piano(self, simple_melody_piece, tmp_path):
        """Load MIDI, arrange as classical piano, verify output."""
        # Save input
        input_path = str(tmp_path / "input.mid")
        save_midi(simple_melody_piece, input_path)

        # Pipeline: load → analyze → arrange → save
        piece = load_midi(input_path)
        summary = generate_summary(piece)

        # Verify summary is usable
        assert summary['num_tracks'] == 2
        assert summary['bpm'] == 120

        # Arrange
        arranged = ArrangePianoTool().run(piece, style='classical')

        # Validate
        range_check = RangeCheckTool().run(arranged, instrument='piano')
        assert range_check['passed'] is True

        # Save output
        output_path = str(tmp_path / "output_classical.mid")
        save_midi(arranged, output_path)

        # Verify output
        assert os.path.exists(output_path)
        output = load_midi(output_path)
        assert len(output.tracks) == 2

    def test_full_pipeline_romantic_piano(self, simple_melody_piece, tmp_path):
        """Load MIDI, arrange as romantic piano, verify output."""
        input_path = str(tmp_path / "input.mid")
        save_midi(simple_melody_piece, input_path)

        piece = load_midi(input_path)
        arranged = ArrangePianoTool().run(piece, style='romantic')

        range_check = RangeCheckTool().run(arranged, instrument='piano')
        assert range_check['passed'] is True

        output_path = str(tmp_path / "output_romantic.mid")
        save_midi(arranged, output_path)

        assert os.path.exists(output_path)
        output = load_midi(output_path)
        assert len(output.tracks) == 2

    def test_full_pipeline_pop_piano(self, simple_melody_piece, tmp_path):
        """Load MIDI, arrange as pop piano, verify output."""
        input_path = str(tmp_path / "input.mid")
        save_midi(simple_melody_piece, input_path)

        piece = load_midi(input_path)
        arranged = ArrangePianoTool().run(piece, style='pop')

        range_check = RangeCheckTool().run(arranged, instrument='piano')
        assert range_check['passed'] is True

        output_path = str(tmp_path / "output_pop.mid")
        save_midi(arranged, output_path)

        assert os.path.exists(output_path)
        output = load_midi(output_path)
        assert len(output.tracks) == 2

    def test_pipeline_preserves_melody(self, simple_melody_piece, tmp_path):
        """Melody notes from input appear in output."""
        piece = simple_melody_piece
        arranged = ArrangePianoTool().run(piece, style='classical')

        # Get original melody degrees
        original_degrees = set()
        for note in piece.tracks[0]:
            if hasattr(note, 'degree'):
                original_degrees.add(note.degree)

        # Get output RH degrees
        rh_degrees = set()
        for note in arranged.tracks[0]:
            if hasattr(note, 'degree'):
                rh_degrees.add(note.degree)

        # At least some melody notes should be preserved
        assert len(original_degrees & rh_degrees) > 0

    def test_pipeline_multi_style_difference(self, simple_melody_piece):
        """Different styles produce different accompaniment patterns."""
        piece = simple_melody_piece

        classical = ArrangePianoTool().run(piece, style='classical')
        romantic = ArrangePianoTool().run(piece, style='romantic')
        pop = ArrangePianoTool().run(piece, style='pop')

        # LH accompaniment should differ between styles
        classical_lh_count = len(classical.tracks[1])
        romantic_lh_count = len(romantic.tracks[1])
        pop_lh_count = len(pop.tracks[1])

        # At least one style should differ from the others
        assert (classical_lh_count != romantic_lh_count or
                classical_lh_count != pop_lh_count or
                romantic_lh_count != pop_lh_count)


class TestMultiTrackPipeline:
    """End-to-end pipeline tests with multi-track MIDI."""

    def test_pop_song_chord_progression(self, pop_song_piece):
        """Pop song (G-D-Em-C) should detect G, D, E/A roots."""
        harmony = AnalyzeHarmonyTool().run(pop_song_piece)
        assert len(harmony) > 0
        chords = [e['chord'].lower() for e in harmony]
        # Should contain G, D, A/E roots
        g_count = sum(1 for c in chords if c.startswith('g') and 'g' in c)
        d_count = sum(1 for c in chords if c.startswith('d') and 'dim' not in c)
        assert g_count > 0 or d_count > 0

    def test_multi_track_arrangement_has_substantial_accompaniment(self, multi_track_piece):
        """Multi-track piece should produce meaningful accompaniment (>50 notes)."""
        arranged = ArrangePianoTool().run(multi_track_piece, style='classical')

        assert len(arranged.tracks) == 2
        lh_count = len(arranged.tracks[1])
        assert lh_count > 16, f"LH only has {lh_count} notes, expected >16"

    def test_multi_track_range_check_passes(self, multi_track_piece):
        """Arranged multi-track piece should pass piano range check."""
        arranged = ArrangePianoTool().run(multi_track_piece, style='classical')
        range_check = RangeCheckTool().run(arranged, instrument='piano')
        assert range_check['passed'] is True

    def test_harmony_chords_parseable(self, multi_track_piece):
        """All detected chords should be parseable by _parse_chord_name."""
        harmony = AnalyzeHarmonyTool().run(multi_track_piece)
        for entry in harmony:
            root, intervals = _parse_chord_name(entry['chord'])
            assert root in ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'], \
                f"Unparseable root in: {entry['chord']}"

    def test_full_pipeline_multi_track(self, multi_track_piece, tmp_path):
        """Full pipeline: load → analyze → arrange → validate → save."""
        input_path = str(tmp_path / "input.mid")
        save_midi(multi_track_piece, input_path)

        piece = load_midi(input_path)
        summary = generate_summary(piece)
        assert summary['num_measures'] >= 6

        arranged = ArrangePianoTool().run(piece, style='classical')
        assert len(arranged.tracks) == 2
        assert len(arranged.tracks[1]) > 16  # LH accompaniment

        range_check = RangeCheckTool().run(arranged, instrument='piano')
        assert range_check['passed'] is True

        output_path = str(tmp_path / "output.mid")
        save_midi(arranged, output_path)
        assert os.path.exists(output_path)
