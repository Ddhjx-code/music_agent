"""
Tests for theory validation / self-correction (Phase 3.3).
"""

import pytest
import musicpy as mp

from tools.validation.theory_check import ValidateTheoryTool, _check_voice_leading, _check_harmony


class TestVoiceLeadingCheck:
    """Test voice leading detection."""

    def test_detects_parallel_fifths(self):
        """Two tracks with parallel fifths should be detected."""
        # Create two tracks: both move in parallel fifths
        track1 = mp.chord([
            mp.note('C', 4, duration=0.5), mp.note('D', 4, duration=0.5),
        ], interval=[0, 0.5])
        track2 = mp.chord([
            mp.note('F', 3, duration=0.5), mp.note('G', 3, duration=0.5),
        ], interval=[0, 0.5])
        piece = mp.P(tracks=[track1, track2], instruments=[1, 1], start_times=[0, 0], bpm=120)

        issues = _check_voice_leading(piece)
        parallel_fifths = [i for i in issues if i['type'] == 'parallel_fifth']
        assert len(parallel_fifths) > 0

    def test_no_parallel_fifths_in_normal_voice(self):
        """SATB-style input should not trigger false positives."""
        track1 = mp.chord([
            mp.note('E', 5, duration=0.5), mp.note('F', 5, duration=0.5),
        ], interval=[0, 0.5])
        track2 = mp.chord([
            mp.note('C', 4, duration=0.5), mp.note('A', 3, duration=0.5),
        ], interval=[0, 0.5])
        piece = mp.P(tracks=[track1, track2], instruments=[1, 1], start_times=[0, 0], bpm=120)

        issues = _check_voice_leading(piece)
        parallel_fifths = [i for i in issues if i['type'] == 'parallel_fifth']
        parallel_octaves = [i for i in issues if i['type'] == 'parallel_octave']
        # This counterpoint (3rd moving to 6th) should be clean
        assert len(parallel_fifths) == 0
        assert len(parallel_octaves) == 0


class TestHarmonyCheck:
    """Test harmony/dissonance detection."""

    def test_detects_tone_clusters(self):
        """3+ consecutive semitones should be flagged."""
        notes = [mp.note('C', 4, duration=0.25), mp.note('C#', 4, duration=0.25), mp.note('D', 4, duration=0.25)]
        track = mp.chord(notes, interval=[0, 0.25, 0.25])
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)

        issues = _check_harmony(piece)
        clusters = [i for i in issues if i['type'] == 'tone_cluster']
        assert len(clusters) > 0

    def test_clean_harmony_no_clusters(self):
        """C major chord should not trigger tone cluster warning."""
        notes = [mp.note('C', 4, duration=1.0), mp.note('E', 4, duration=1.0), mp.note('G', 4, duration=1.0)]
        track = mp.chord(notes, interval=[0, 0, 0])
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)

        issues = _check_harmony(piece)
        clusters = [i for i in issues if i['type'] == 'tone_cluster']
        assert len(clusters) == 0


class TestValidateTheoryTool:
    """Test the unified validation tool."""

    def test_clean_piece_passes(self, simple_melody_piece):
        """Simple melody piece should pass without errors."""
        tool = ValidateTheoryTool()
        result = tool.run(simple_melody_piece)
        assert result['passed'], f"Should pass: {result['summary']}"

    def test_returns_summary_string(self, simple_melody_piece):
        """Should return a human-readable summary."""
        tool = ValidateTheoryTool()
        result = tool.run(simple_melody_piece)
        assert 'summary' in result
        assert isinstance(result['summary'], str)
        assert len(result['summary']) > 0

    def test_out_of_range_triggers_error(self):
        """Notes outside piano range should trigger error."""
        notes = [mp.note('C', 0, duration=0.5)]  # C0 = MIDI 12, below piano A0=21
        track = mp.chord(notes, interval=[0])
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)

        tool = ValidateTheoryTool()
        result = tool.run(piece, instrument='piano')
        assert not result['passed']
        errors = [i for i in result['issues'] if i.get('severity') == 'error']
        assert len(errors) > 0

    def test_parallel_fifths_warning(self):
        """Parallel fifths should be warning, not error."""
        track1 = mp.chord([
            mp.note('C', 4, duration=0.5), mp.note('D', 4, duration=0.5),
        ], interval=[0, 0.5])
        track2 = mp.chord([
            mp.note('F', 3, duration=0.5), mp.note('G', 3, duration=0.5),
        ], interval=[0, 0.5])
        piece = mp.P(tracks=[track1, track2], instruments=[1, 1], start_times=[0, 0], bpm=120)

        tool = ValidateTheoryTool()
        result = tool.run(piece)
        warnings = [i for i in result['issues'] if i.get('severity') == 'warning']
        assert len(warnings) > 0

    def test_empty_piece_handled(self):
        """Empty piece should pass."""
        tool = ValidateTheoryTool()
        empty = mp.P(tracks=[], instruments=[], start_times=[], bpm=120)
        result = tool.run(empty)
        assert result['passed']
