"""
Tests for Phase 3 expression tools: sustain pedal, velocity, timing variation.
"""

import pytest
import musicpy as mp

from tools.expression.add_pedal import AddSustainPedalTool
from tools.expression.adjust_velocity import AdjustVelocityTool
from tools.expression.timing_variation import ApplyTimingVariationTool


class TestAddSustainPedalTool:
    """Test sustain pedal insertion tool."""

    def test_creates_pedal_events_at_chord_changes(self, simple_melody_piece):
        """Should create sustain pedal events at harmonic change points."""
        tool = AddSustainPedalTool()
        result = tool.run(simple_melody_piece)
        # Result should have pedal events (CC#64)
        pedal_events = self._count_pedal_events(result)
        assert pedal_events > 0, "Should have sustain pedal events"

    def test_pedal_on_then_off(self, simple_melody_piece):
        """Pedal should have on/off pairs (value 127 then 0)."""
        tool = AddSustainPedalTool()
        result = tool.run(simple_melody_piece)
        events = self._get_pedal_events(result)
        # Should have both pedal on (127) and off (0) events
        values = [e.value for e in events]
        assert 127 in values, "Should have pedal on (127) events"
        assert 0 in values, "Should have pedal off (0) events"

    def test_empty_piece_handled(self):
        """Empty piece should be handled gracefully."""
        tool = AddSustainPedalTool()
        empty = mp.P(tracks=[], instruments=[], start_times=[], bpm=120)
        result = tool.run(empty)
        assert result is not None

    def test_preserves_note_count(self, simple_melody_piece):
        """Pedal insertion should not change note count."""
        original_notes = sum(len(list(t)) for t in simple_melody_piece.tracks)
        tool = AddSustainPedalTool()
        result = tool.run(simple_melody_piece)
        result_notes = sum(len(list(t)) for t in result.tracks)
        assert result_notes == original_notes

    def test_preserves_bpm(self, simple_melody_piece):
        """BPM should be preserved after pedal insertion."""
        tool = AddSustainPedalTool()
        result = tool.run(simple_melody_piece)
        assert result.bpm == 120

    @staticmethod
    def _count_pedal_events(piece) -> int:
        if not hasattr(piece, 'other_messages'):
            return 0
        return sum(1 for m in piece.other_messages
                   if hasattr(m, 'control') and m.control == 64)

    @staticmethod
    def _get_pedal_events(piece) -> list:
        if not hasattr(piece, 'other_messages'):
            return []
        return [m for m in piece.other_messages
                if hasattr(m, 'control') and m.control == 64]


class TestAdjustVelocityTool:
    """Test velocity (volume) adjustment tool."""

    def test_boost_melody_velocity(self, simple_melody_piece):
        """Should increase melody track velocity."""
        orig_avg = self._avg_velocity(simple_melody_piece.tracks[0])
        tool = AdjustVelocityTool()
        result = tool.run(simple_melody_piece, melody_boost=10)
        new_avg = self._avg_velocity(result.tracks[0])
        assert new_avg > orig_avg, f"Melody velocity should increase: {orig_avg} -> {new_avg}"

    def test_reduce_accompaniment_velocity(self, simple_melody_piece):
        """Should decrease accompaniment track velocity."""
        orig_avg = self._avg_velocity(simple_melody_piece.tracks[1])
        tool = AdjustVelocityTool()
        result = tool.run(simple_melody_piece, accompaniment_reduce=10)
        new_avg = self._avg_velocity(result.tracks[1])
        assert new_avg < orig_avg, f"Accompaniment velocity should decrease: {orig_avg} -> {new_avg}"

    def test_combined_boost_and_reduce(self, simple_melody_piece):
        """Should create dynamic contrast between melody and accompaniment."""
        tool = AdjustVelocityTool()
        result = tool.run(simple_melody_piece, melody_boost=15, accompaniment_reduce=10)
        melody_vel = self._avg_velocity(result.tracks[0])
        accomp_vel = self._avg_velocity(result.tracks[1])
        assert melody_vel > accomp_vel + 10, "Melody should be significantly louder than accompaniment"

    def test_velocity_clamped_to_valid_range(self, simple_melody_piece):
        """Velocity should be clamped to 1-127 range."""
        tool = AdjustVelocityTool()
        result = tool.run(simple_melody_piece, melody_boost=200)  # Way too much
        for track in result.tracks:
            for note in track:
                if hasattr(note, 'volume'):
                    assert 1 <= note.volume <= 127, f"Velocity {note.volume} out of range"

    def test_no_change_when_zero_boost(self, simple_melody_piece):
        """No change when boost and reduce are both 0."""
        tool = AdjustVelocityTool()
        result = tool.run(simple_melody_piece, melody_boost=0, accompaniment_reduce=0)
        orig_vel = [n.volume for t in simple_melody_piece.tracks for n in t if hasattr(n, 'volume')]
        new_vel = [n.volume for t in result.tracks for n in t if hasattr(n, 'volume')]
        assert orig_vel == new_vel, "No change when boost/reduce are zero"

    def test_preserves_bpm(self, simple_melody_piece):
        """BPM should be preserved."""
        tool = AdjustVelocityTool()
        result = tool.run(simple_melody_piece, melody_boost=10)
        assert result.bpm == 120

    @staticmethod
    def _avg_velocity(track) -> float:
        vols = [n.volume for n in track if hasattr(n, 'volume')]
        return sum(vols) / len(vols) if vols else 0


class TestApplyTimingVariationTool:
    """Test timing variation tool (rubato, swing)."""

    def test_rubato_adds_timing_variation(self, simple_melody_piece):
        """Rubato should alter note timing intervals."""
        orig_intervals = list(getattr(simple_melody_piece.tracks[0], 'interval', []))
        tool = ApplyTimingVariationTool()
        result = tool.run(simple_melody_piece, type='rubato', amount=0.05)
        new_intervals = list(getattr(result.tracks[0], 'interval', []))
        # Should differ from original (rubato changes timing)
        if orig_intervals and new_intervals:
            assert orig_intervals != new_intervals, "Rubato should change note timings"

    def test_swing_makes_unequal_eighths(self, simple_melody_piece):
        """Swing should make even-numbered eighth notes longer."""
        tool = ApplyTimingVariationTool()
        result = tool.run(simple_melody_piece, type='swing', amount=0.15)
        # Swing should produce different intervals
        orig = list(getattr(simple_melody_piece.tracks[0], 'interval', []))
        new = list(getattr(result.tracks[0], 'interval', []))
        if orig and new:
            assert orig != new, "Swing should change note timing"

    def test_preserves_note_count(self, simple_melody_piece):
        """Should not add or remove notes."""
        tool = ApplyTimingVariationTool()
        orig_count = sum(len(list(t)) for t in simple_melody_piece.tracks)
        result = tool.run(simple_melody_piece, type='rubato', amount=0.05)
        new_count = sum(len(list(t)) for t in result.tracks)
        assert orig_count == new_count, "Note count should be preserved"

    def test_preserves_bpm(self, simple_melody_piece):
        """BPM should be preserved."""
        tool = ApplyTimingVariationTool()
        result = tool.run(simple_melody_piece, type='swing', amount=0.1)
        assert result.bpm == 120

    def test_preserves_degrees(self, simple_melody_piece):
        """Note pitches should not change — only timing."""
        tool = ApplyTimingVariationTool()
        orig_degrees = [n.degree for t in simple_melody_piece.tracks for n in t if hasattr(n, 'degree')]
        result = tool.run(simple_melody_piece, type='rubato', amount=0.05)
        new_degrees = [n.degree for t in result.tracks for n in t if hasattr(n, 'degree')]
        assert orig_degrees == new_degrees, "Rubato should not change pitches"

    def test_invalid_type_raises(self, simple_melody_piece):
        """Invalid variation type should raise ValueError."""
        tool = ApplyTimingVariationTool()
        with pytest.raises(ValueError):
            tool.run(simple_melody_piece, type='invalid_type')

    def test_preserves_volumes(self, simple_melody_piece):
        """Note volumes should not change."""
        tool = ApplyTimingVariationTool()
        orig_vols = [n.volume for t in simple_melody_piece.tracks for n in t if hasattr(n, 'volume')]
        result = tool.run(simple_melody_piece, type='rubato', amount=0.05)
        new_vols = [n.volume for t in result.tracks for n in t if hasattr(n, 'volume')]
        assert orig_vols == new_vols, "Rubato should not change volumes"
