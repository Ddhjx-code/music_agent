"""
Tests for ArrangeStringsTool — string quartet arrangement.

Tests:
- 4-voice input produces 4 tracks
- Output has correct GM programs [40, 40, 41, 42]
- Per-instrument range validation
- Single-track input derives 4 voices
- Two-track input creates quartet
- Bass line maps to cello
- Empty piece handled gracefully
"""

import pytest
import musicpy as mp

from tools.arrangement.arrange_strings import ArrangeStringsTool


class TestArrangeStringsTool:
    """Test string quartet arrangement tool."""

    def test_four_voice_input_produces_four_tracks(self, four_voice_piece):
        """4-voice input should produce 4 output tracks."""
        tool = ArrangeStringsTool()
        result = tool.run(four_voice_piece)
        assert len(result.tracks) == 4

    def test_output_has_correct_gm_programs(self, four_voice_piece):
        """Programs should be [40, 40, 41, 42] for Vln1, Vln2, Vla, Vcl."""
        tool = ArrangeStringsTool()
        result = tool.run(four_voice_piece)
        assert result.instruments[:4] == [40, 40, 41, 42]

    def test_violin1_range_valid(self, four_voice_piece):
        """Vln1 notes should be within G3-A7 (67-115)."""
        tool = ArrangeStringsTool()
        result = tool.run(four_voice_piece)
        low, high = 67, 115
        for note in result.tracks[0]:
            if hasattr(note, 'degree'):
                assert low <= note.degree <= high, f"Vln1 note {note.name}{note.num} MIDI {note.degree} out of range"

    def test_viola_range_valid(self, four_voice_piece):
        """Viola notes should be within C3-E6 (48-93)."""
        tool = ArrangeStringsTool()
        result = tool.run(four_voice_piece)
        low, high = 48, 93
        for note in result.tracks[2]:
            if hasattr(note, 'degree'):
                assert low <= note.degree <= high, f"Viola note out of range: MIDI {note.degree}"

    def test_cello_range_valid(self, four_voice_piece):
        """Cello notes should be within C2-A5 (36-88)."""
        tool = ArrangeStringsTool()
        result = tool.run(four_voice_piece)
        low, high = 36, 88
        for note in result.tracks[3]:
            if hasattr(note, 'degree'):
                assert low <= note.degree <= high, f"Cello note out of range: MIDI {note.degree}"

    def test_single_track_input_extracts_four_voices(self, single_track_piece):
        """Monophonic input should derive 4 tracks via harmony analysis."""
        tool = ArrangeStringsTool()
        result = tool.run(single_track_piece)
        assert len(result.tracks) == 4

    def test_two_track_input_creates_quartet(self, simple_melody_piece):
        """Melody + chords input should create 4 tracks."""
        tool = ArrangeStringsTool()
        result = tool.run(simple_melody_piece)
        assert len(result.tracks) == 4

    def test_bass_line_maps_to_cello(self, four_voice_piece):
        """Lowest input voice should map to cello track (track index 3)."""
        tool = ArrangeStringsTool()
        result = tool.run(four_voice_piece)
        cello_track = result.tracks[3]
        # Cello track should have lower average pitch than violin 1
        cello_degrees = [n.degree for n in cello_track if hasattr(n, 'degree')]
        vln1_degrees = [n.degree for n in result.tracks[0] if hasattr(n, 'degree')]
        if cello_degrees and vln1_degrees:
            assert sum(cello_degrees) / len(cello_degrees) < sum(vln1_degrees) / len(vln1_degrees)

    def test_empty_piece_returns_empty_tracks(self):
        """Empty input should return 4 empty tracks."""
        tool = ArrangeStringsTool()
        empty = mp.P(tracks=[], instruments=[], start_times=[], bpm=120)
        result = tool.run(empty)
        assert len(result.tracks) == 4

    def test_preserves_bpm(self, four_voice_piece):
        """Output BPM should match input."""
        tool = ArrangeStringsTool()
        result = tool.run(four_voice_piece)
        assert result.bpm == 120
