"""Tests for core/audio_postprocess.py."""

import musicpy as mp
import pytest

from core.audio_postprocess import (
    estimate_tempo, quantize_rhythm, normalize_velocities,
    remove_duplicate_notes, cleanup_durations, postprocess_midi
)


class TestEstimateTempo:
    """Test BPM estimation from note onsets."""

    def test_estimates_120_bpm(self):
        notes = [mp.note('C', 4, duration=0.25) for _ in range(8)]
        intervals = [0.0] + [0.5] * 7
        track = mp.chord(notes, interval=intervals)
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=60)
        bpm = estimate_tempo(piece)
        assert abs(bpm - 120) < 10, f"Expected ~120, got {bpm}"

    def test_returns_default_on_empty(self):
        piece = mp.P(tracks=[], instruments=[], start_times=[], bpm=120)
        bpm = estimate_tempo(piece, default_bpm=100)
        assert bpm == 100

    def test_estimates_90_bpm(self):
        notes = [mp.note('C', 4, duration=0.25) for _ in range(8)]
        intervals = [0.0] + [2.0/3] * 7
        track = mp.chord(notes, interval=intervals)
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=60)
        bpm = estimate_tempo(piece)
        assert abs(bpm - 90) < 10, f"Expected ~90, got {bpm}"


class TestQuantizeRhythm:
    """Test rhythm quantization."""

    def test_snaps_to_quarter_grid(self):
        notes = [
            mp.note('C', 4, duration=0.25),
            mp.note('D', 4, duration=0.25),
            mp.note('E', 4, duration=0.25),
        ]
        intervals = [0.0, 0.48, 0.52]
        track = mp.chord(notes, interval=intervals)
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)
        result = quantize_rhythm(piece, subdivision=0.25)
        new_intervals = getattr(result.tracks[0], 'interval', [])
        assert abs(new_intervals[1] - 0.5) < 0.01
        assert abs(new_intervals[2] - 0.5) < 0.01

    def test_preserves_first_note_timing(self):
        notes = [mp.note('C', 4, duration=0.25)]
        track = mp.chord(notes, interval=[0.0])
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)
        result = quantize_rhythm(piece, subdivision=0.25)
        intervals = getattr(result.tracks[0], 'interval', [])
        assert intervals[0] == 0.0

    def test_handles_empty_track(self):
        piece = mp.P(tracks=[], instruments=[], start_times=[], bpm=120)
        result = quantize_rhythm(piece)
        assert result is not None


class TestNormalizeVelocities:
    """Test velocity normalization."""

    def test_scales_to_range(self):
        notes = [mp.note('C', 4, duration=0.25), mp.note('D', 4, duration=0.25)]
        notes[0].volume = 10
        notes[1].volume = 127
        track = mp.chord(notes, interval=[0.0, 0.25])
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)
        result = normalize_velocities(piece, min_vel=40, max_vel=110)
        velocities = [n.volume for n in result.tracks[0] if hasattr(n, 'volume')]
        assert all(40 <= v <= 110 for v in velocities)

    def test_preserves_relative_dynamics(self):
        notes = [mp.note('C', 4, duration=0.25) for _ in range(3)]
        notes[0].volume = 30
        notes[1].volume = 60
        notes[2].volume = 90
        track = mp.chord(notes, interval=[0.0, 0.25, 0.25])
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)
        result = normalize_velocities(piece)
        velocities = [n.volume for n in result.tracks[0]]
        assert velocities[0] < velocities[1] < velocities[2]


class TestRemoveDuplicateNotes:
    """Test duplicate note removal."""

    def test_removes_same_pitch_overlap(self):
        notes = [mp.note('C', 4, duration=0.25), mp.note('C', 4, duration=0.5)]
        notes[0].volume = 60
        notes[1].volume = 70
        track = mp.chord(notes, interval=[0.0, 0.05])
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)
        result = remove_duplicate_notes(piece, threshold=0.1)
        count = len([n for t in result.tracks for n in (t.notes if hasattr(t, 'notes') else list(t))])
        assert count == 1

    def test_keeps_different_pitches(self):
        notes = [mp.note('C', 4, duration=0.25), mp.note('D', 4, duration=0.25)]
        notes[0].volume = 60
        notes[1].volume = 70
        track = mp.chord(notes, interval=[0.0, 0.25])
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)
        result = remove_duplicate_notes(piece)
        count = len([n for t in result.tracks for n in (t.notes if hasattr(t, 'notes') else list(t))])
        assert count == 2


class TestCleanupDurations:
    """Test note duration cleanup."""

    def test_normalizes_to_musical_values(self):
        notes = [mp.note('C', 4, duration=0.23)]
        track = mp.chord(notes, interval=[0.0])
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)
        result = cleanup_durations(piece)
        note = list(result.tracks[0])[0]
        assert abs(note.duration - 0.25) < 0.01


class TestPostprocessMidi:
    """Test full postprocessing pipeline."""

    def test_runs_all_steps(self, simple_melody_piece):
        result = postprocess_midi(simple_melody_piece)
        assert len(result.tracks) == len(simple_melody_piece.tracks)
        for track in result.tracks:
            for note in (track.notes if hasattr(track, 'notes') else list(track)):
                if hasattr(note, 'volume'):
                    assert 40 <= note.volume <= 110
