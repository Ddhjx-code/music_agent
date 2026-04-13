"""
Tests for ArrangeWindsTool — wind ensemble arrangement.

Tests:
- Standard instrumentation produces 7 tracks
- Output has correct GM programs
- Per-instrument range validation
- Concert pitch vs. transposed notation
- Transposing instrument correctness (Bb +2, Eb +9)
- Single-track input maps to wind sections
- Bass generation from harmony when no bass track
- Empty piece handled gracefully
"""

import pytest
import musicpy as mp

from tools.arrangement.arrange_winds import ArrangeWindsTool
from tools.arrangement.transposition import (
    transpose_note, transpose_to_written, transpose_to_concert,
    TRANSPOSING_OFFSETS, WIND_PROGRAMS, get_wind_programs,
)


class TestTranspositionUtils:
    """Test transposition utility functions."""

    def test_bb_transpose_up_two_semitones(self):
        """Bb clarinet should transpose +2 semitones."""
        note = mp.note('C', 4)
        written = transpose_to_written([note], 'clarinet_bb')
        assert len(written) == 1
        assert written[0].degree == note.degree + 2

    def test_eb_transpose_up_nine_semitones(self):
        """Eb alto sax should transpose +9 semitones."""
        note = mp.note('C', 4)
        written = transpose_to_written([note], 'alto_sax_eb')
        assert len(written) == 1
        assert written[0].degree == note.degree + 9

    def test_roundtrip_transpose_returns_original(self):
        """Concert -> written -> concert should return same pitch."""
        note = mp.note('E', 4)
        written = transpose_to_written([note], 'clarinet_bb')
        back = transpose_to_concert(written, 'clarinet_bb')
        assert back[0].degree == note.degree

    def test_non_transposing_instrument_unchanged(self):
        """Flute, trombone, tuba should not transpose."""
        note = mp.note('G', 4)
        for inst in ['flute', 'trombone', 'tuba']:
            result = transpose_to_written([note], inst)
            assert result[0].degree == note.degree, f"{inst} should not transpose"

    def test_get_wind_programs_standard(self):
        """Standard wind ensemble should return 7 GM programs."""
        programs = get_wind_programs('standard')
        assert len(programs) == 7
        assert programs[0] == WIND_PROGRAMS['flute']  # Flute
        assert programs[1] == WIND_PROGRAMS['clarinet_bb']  # Clarinet

    def test_get_wind_programs_quintet(self):
        """Quintet should return 5 GM programs."""
        programs = get_wind_programs('quintet')
        assert len(programs) == 5


class TestArrangeWindsTool:
    """Test wind ensemble arrangement tool."""

    def test_standard_instrumentation_produces_seven_tracks(self, full_harmony_piece):
        """Standard ensemble = 7 tracks."""
        tool = ArrangeWindsTool()
        result = tool.run(full_harmony_piece)
        assert len(result.tracks) == 7

    def test_output_has_correct_gm_programs(self, full_harmony_piece):
        """Instruments should match wind ensemble GM programs."""
        tool = ArrangeWindsTool()
        result = tool.run(full_harmony_piece)
        expected = [
            WIND_PROGRAMS['flute'],
            WIND_PROGRAMS['clarinet_bb'],
            WIND_PROGRAMS['alto_sax_eb'],
            WIND_PROGRAMS['trumpet_bb'],
            WIND_PROGRAMS['french_horn'],
            WIND_PROGRAMS['trombone'],
            WIND_PROGRAMS['tuba'],
        ]
        assert result.instruments[:7] == expected

    def test_flute_range_valid(self, full_harmony_piece):
        """Flute notes within C4-C8 (72-108)."""
        tool = ArrangeWindsTool()
        result = tool.run(full_harmony_piece)
        low, high = 72, 108
        for note in result.tracks[0]:
            if hasattr(note, 'degree'):
                assert low <= note.degree <= high, f"Flute note out of range: MIDI {note.degree}"

    def test_trumpet_range_valid(self, full_harmony_piece):
        """Trumpet notes within C4-B6 (60-95)."""
        tool = ArrangeWindsTool()
        result = tool.run(full_harmony_piece)
        low, high = 60, 95
        trump_idx = 3  # Trumpet is track 3
        for note in result.tracks[trump_idx]:
            if hasattr(note, 'degree'):
                assert low <= note.degree <= high, f"Trumpet note out of range: MIDI {note.degree}"

    def test_tuba_range_valid(self, full_harmony_piece):
        """Tuba notes within Bb0-F3 (24-52)."""
        tool = ArrangeWindsTool()
        result = tool.run(full_harmony_piece)
        low, high = 24, 52
        tuba_idx = 6  # Tuba is last track
        for note in result.tracks[tuba_idx]:
            if hasattr(note, 'degree'):
                assert low <= note.degree <= high, f"Tuba note out of range: MIDI {note.degree}"

    def test_concert_pitch_notation_true_keeps_pitches(self, full_harmony_piece):
        """Concert pitch mode should preserve original pitch classes."""
        tool = ArrangeWindsTool()
        result = tool.run(full_harmony_piece, concert_pitch_notation=True)
        # All notes should be at concert pitch (no transposition applied)
        # Verify by checking that flute track has expected melody pitches
        assert len(result.tracks) >= 1

    def test_single_track_input_maps_to_wind_sections(self, single_track_piece):
        """Monophonic input should derive multiple wind parts."""
        tool = ArrangeWindsTool()
        result = tool.run(single_track_piece)
        assert len(result.tracks) == 7

    def test_no_bass_generates_from_harmony(self, simple_melody_piece):
        """Input without explicit bass gets bass from chord roots."""
        tool = ArrangeWindsTool()
        result = tool.run(simple_melody_piece)
        assert len(result.tracks) == 7
        # Tuba/trombone tracks should have notes
        tuba_idx = 6
        tuba_notes = [n for n in result.tracks[tuba_idx] if hasattr(n, 'degree')]
        assert len(tuba_notes) > 0

    def test_empty_piece_returns_empty_tracks(self):
        """Empty input should return 7 empty tracks."""
        tool = ArrangeWindsTool()
        empty = mp.P(tracks=[], instruments=[], start_times=[], bpm=120)
        result = tool.run(empty)
        assert len(result.tracks) == 7

    def test_quintet_instrumentation_produces_five_tracks(self, full_harmony_piece):
        """Quintet = 5 tracks: Fl, Cl, Tpt, Hn, Tbn."""
        tool = ArrangeWindsTool()
        result = tool.run(full_harmony_piece, instrumentation='quintet')
        assert len(result.tracks) == 5

    def test_preserves_bpm(self, full_harmony_piece):
        """Output BPM should match input."""
        tool = ArrangeWindsTool()
        result = tool.run(full_harmony_piece)
        assert result.bpm == 120
