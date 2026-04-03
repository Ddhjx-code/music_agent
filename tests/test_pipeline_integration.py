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
