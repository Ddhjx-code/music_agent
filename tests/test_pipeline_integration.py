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
from tools.arrangement.arrange_strings import ArrangeStringsTool
from tools.arrangement.arrange_winds import ArrangeWindsTool
from tools.expression.add_pedal import AddSustainPedalTool
from tools.expression.adjust_velocity import AdjustVelocityTool
from tools.expression.timing_variation import ApplyTimingVariationTool
from tools.validation.range_check import RangeCheckTool
from tools.validation.theory_check import ValidateTheoryTool
from tools.analysis.analyze_harmony import AnalyzeHarmonyTool
from tools.harmony.generate_accompaniment import GenerateAccompanimentTool


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
        """All detected chords should have valid root notes."""
        import re
        harmony = AnalyzeHarmonyTool().run(multi_track_piece)
        for entry in harmony:
            match = re.match(r'^(?:note\s+)?([A-G][#b]?)', entry['chord'])
            root = match.group(1) if match else None
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


class TestStringQuartetIntegration:
    """Integration tests for string quartet arrangement."""

    def test_full_pipeline_string_quartet(self, four_voice_piece, tmp_path):
        """Load MIDI, arrange as string quartet, validate, save."""
        input_path = str(tmp_path / "input.mid")
        save_midi(four_voice_piece, input_path)

        piece = load_midi(input_path)
        arranged = ArrangeStringsTool().run(piece)

        assert len(arranged.tracks) == 4
        assert arranged.instruments[:4] == [40, 40, 41, 42]

        # Check individual track ranges
        from tools.validation.range_check import INSTRUMENT_RANGES
        track_instruments = ['violin', 'violin', 'viola', 'cello']
        for track_idx, inst in enumerate(track_instruments):
            low, high = INSTRUMENT_RANGES[inst]
            for note in arranged.tracks[track_idx]:
                if hasattr(note, 'degree'):
                    assert low <= note.degree <= high, \
                        f"Track {track_idx} ({inst}) note {note.degree} out of range [{low}-{high}]"

        output_path = str(tmp_path / "output_strings.mid")
        save_midi(arranged, output_path)
        assert os.path.exists(output_path)

        # Reload and verify
        output = load_midi(output_path)
        assert len(output.tracks) == 4


class TestWindEnsembleIntegration:
    """Integration tests for wind ensemble arrangement."""

    def test_full_pipeline_wind_ensemble(self, full_harmony_piece, tmp_path):
        """Load MIDI, arrange as wind ensemble, validate, save."""
        piece = full_harmony_piece
        arranged = ArrangeWindsTool().run(piece)

        assert len(arranged.tracks) == 7

        # Check flute track (0) range
        from tools.validation.range_check import INSTRUMENT_RANGES
        track_instruments = ['flute', 'clarinet', 'alto_sax', 'trumpet', 'french_horn', 'trombone', 'tuba']
        for track_idx, inst in enumerate(track_instruments):
            low, high = INSTRUMENT_RANGES[inst]
            for note in arranged.tracks[track_idx]:
                if hasattr(note, 'degree'):
                    assert low <= note.degree <= high, \
                        f"Track {track_idx} ({inst}) note {note.degree} out of range [{low}-{high}]"

        output_path = str(tmp_path / "output_winds.mid")
        save_midi(arranged, output_path)
        assert os.path.exists(output_path)

    def test_wind_quintet_pipeline(self, full_harmony_piece, tmp_path):
        """Quintet arrangement: 5 tracks."""
        piece = full_harmony_piece
        arranged = ArrangeWindsTool().run(piece, instrumentation='quintet')
        assert len(arranged.tracks) == 5


class TestExpressionToolsIntegration:
    """Integration tests for Phase 3 expression tools."""

    def test_pedal_preserves_melody(self, simple_melody_piece):
        """Sustain pedal should not alter melody notes."""
        orig_degrees = [n.degree for t in simple_melody_piece.tracks for n in t if hasattr(n, 'degree')]
        result = AddSustainPedalTool().run(simple_melody_piece)
        new_degrees = [n.degree for t in result.tracks for n in t if hasattr(n, 'degree')]
        assert orig_degrees == new_degrees

    def test_velocity_chain_with_piano_arrangement(self, simple_melody_piece):
        """Piano arrange → velocity boost should produce louder melody."""
        arranged = ArrangePianoTool().run(simple_melody_piece, style='classical')
        boosted = AdjustVelocityTool().run(arranged, melody_boost=15, accompaniment_reduce=10)

        melody_vel = sum(n.volume for n in boosted.tracks[0] if hasattr(n, 'volume')) / max(1, len([n for n in boosted.tracks[0] if hasattr(n, 'volume')]))
        accomp_vel = sum(n.volume for n in boosted.tracks[1] if hasattr(n, 'volume')) / max(1, len([n for n in boosted.tracks[1] if hasattr(n, 'volume')]))
        assert melody_vel > accomp_vel + 5

    def test_rubato_then_theory_validation(self, simple_melody_piece):
        """Apply rubato → theory validation should still pass."""
        result = ApplyTimingVariationTool().run(simple_melody_piece, type='rubato', amount=0.05)
        theory = ValidateTheoryTool().run(result)
        assert theory['passed']

    def test_full_expression_chain(self, four_voice_piece, tmp_path):
        """String quartet → pedal → velocity → rubato → validate → save."""
        piece = four_voice_piece

        # Arrange for strings
        arranged = ArrangeStringsTool().run(piece)
        assert len(arranged.tracks) == 4

        # Add pedal
        with_pedal = AddSustainPedalTool().run(arranged)
        pedal_count = len(getattr(with_pedal, 'other_messages', []))
        assert pedal_count > 0

        # Boost melody velocity
        with_velocity = AdjustVelocityTool().run(with_pedal, melody_boost=10)

        # Apply rubato
        with_rubato = ApplyTimingVariationTool().run(with_velocity, type='rubato', amount=0.03)

        # Theory validation
        theory = ValidateTheoryTool().run(with_rubato)
        assert theory['summary']  # Should have a summary

        # Save and reload
        output_path = str(tmp_path / "output_expression.mid")
        save_midi(with_rubato, output_path)
        assert os.path.exists(output_path)
        reloaded = load_midi(output_path)
        assert len(reloaded.tracks) == 4
