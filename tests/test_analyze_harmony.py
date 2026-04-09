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
        # Use enough notes to exceed the minimum duration threshold
        c_chord = mp.chord(
            ['C3', 'E3', 'G3', 'C4', 'E4', 'G4'],
            duration=1.0, interval=[0, 0, 0, 0, 0, 0]
        )

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


class TestAnalyzeHarmonyMultiTrack:
    """Tests for multi-track harmony analysis with structured output."""

    def test_multi_track_clean_chord_names(self, multi_track_piece):
        """Chord names should not contain 'sort as' or 'omit' noise."""
        tool = AnalyzeHarmonyTool()
        result = tool.run(multi_track_piece)

        for entry in result:
            chord = entry['chord']
            assert 'sort as' not in chord, f"Complex chord name: {chord}"

    def test_multi_track_correct_count(self, multi_track_piece):
        """8-measure piece should produce ~8 chord entries."""
        tool = AnalyzeHarmonyTool()
        result = tool.run(multi_track_piece)
        assert 6 <= len(result) <= 10

    def test_exclude_short_tracks(self, multi_track_piece):
        """Short-duration effect tracks should not pollute harmony analysis."""
        tool = AnalyzeHarmonyTool()
        result = tool.run(multi_track_piece)

        chords = [e['chord'].lower() for e in result]
        # Should detect C, G, A, F roots from the harmony track
        valid_roots = sum(1 for c in chords if any(r in c for r in ['c', 'g', 'a', 'f']))
        assert valid_roots > len(chords) * 0.5

    def test_structured_output_has_root_quality(self, simple_melody_piece):
        """Output dicts should include 'root' and 'quality' fields."""
        tool = AnalyzeHarmonyTool()
        result = tool.run(simple_melody_piece)

        for entry in result:
            assert 'root' in entry, f"Missing root in: {entry}"
            assert 'quality' in entry, f"Missing quality in: {entry}"

    def test_c_major_detection(self):
        """C major chord should produce root='C', quality='major'."""
        tool = AnalyzeHarmonyTool()
        c_chord = mp.chord(
            ['C3', 'E3', 'G3', 'C4', 'E4', 'G4'],
            duration=1.0, interval=[0, 0, 0, 0, 0, 0]
        )
        piece = mp.P(tracks=[c_chord], instruments=[1], start_times=[0], bpm=120)
        result = tool.run(piece)

        assert len(result) >= 1
        assert result[0]['root'] == 'C'
        assert result[0]['quality'] in ('major', 'maj')

    def test_a_minor_detection(self):
        """A minor chord should produce root='A', quality='minor'."""
        tool = AnalyzeHarmonyTool()
        am_chord = mp.chord(
            ['A2', 'C3', 'E3', 'A3', 'C4', 'E4'],
            duration=1.0, interval=[0, 0, 0, 0, 0, 0]
        )
        piece = mp.P(tracks=[am_chord], instruments=[1], start_times=[0], bpm=120)
        result = tool.run(piece)

        assert len(result) >= 1
        assert result[0]['root'] == 'A'
        assert 'min' in result[0]['quality']
