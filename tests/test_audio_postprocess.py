"""Tests for core/audio_postprocess.py."""

import musicpy as mp
import pytest

from core.audio_postprocess import (
    estimate_tempo, normalize_velocities,
    postprocess_midi, extract_melody_pipeline,
    _sustained_note_merge, estimate_tempo_enhanced,
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


class TestSustainedNoteMerge:
    """Test transcription fragment merging."""

    def test_merges_same_pitch_close_notes(self):
        """Two same-pitch notes very close together should merge."""
        notes = [mp.note('C', 4, duration=0.1), mp.note('C', 4, duration=0.15)]
        notes[0].volume = 60
        notes[1].volume = 70
        track = mp.chord(notes, interval=[0.0, 0.05])
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)
        result = _sustained_note_merge(piece, window=0.3)
        count = len(result.tracks[0].notes if hasattr(result.tracks[0], 'notes') else list(result.tracks[0]))
        assert count == 1

    def test_keeps_different_pitches(self):
        """Different pitches should not merge."""
        notes = [mp.note('C', 4, duration=0.25), mp.note('D', 4, duration=0.25)]
        notes[0].volume = 60
        notes[1].volume = 70
        track = mp.chord(notes, interval=[0.0, 0.25])
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)
        result = _sustained_note_merge(piece, window=0.3)
        count = len(result.tracks[0].notes if hasattr(result.tracks[0], 'notes') else list(result.tracks[0]))
        assert count == 2

    def test_keeps_widely_spaced_same_pitch(self):
        """Same pitch but far apart should remain separate (melody repetition)."""
        notes = [mp.note('C', 4, duration=0.25), mp.note('C', 4, duration=0.25)]
        notes[0].volume = 60
        notes[1].volume = 70
        track = mp.chord(notes, interval=[0.0, 1.0])
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)
        result = _sustained_note_merge(piece, window=0.3)
        count = len(result.tracks[0].notes if hasattr(result.tracks[0], 'notes') else list(result.tracks[0]))
        assert count == 2

    def test_handles_empty_piece(self):
        piece = mp.P(tracks=[], instruments=[], start_times=[], bpm=120)
        result = _sustained_note_merge(piece)
        assert len(result.tracks) == 0


class TestPostprocessMidi:
    """Test full postprocessing pipeline."""

    def test_runs_all_steps(self, simple_melody_piece):
        result = postprocess_midi(simple_melody_piece)
        assert len(result.tracks) == len(simple_melody_piece.tracks)
        for track in result.tracks:
            for note in (track.notes if hasattr(track, 'notes') else list(track)):
                if hasattr(note, 'volume'):
                    assert 40 <= note.volume <= 110

    def test_normalizes_velocities(self, simple_melody_piece):
        """postprocess_midi should normalize velocities to the configured range."""
        result = postprocess_midi(simple_melody_piece)
        for track in result.tracks:
            for note in (track.notes if hasattr(track, 'notes') else list(track)):
                if hasattr(note, 'volume'):
                    assert 40 <= note.volume <= 110


class TestExtractMelodyPipeline:
    """Test the enhanced melody extraction pipeline."""

    def test_detects_key_from_clean_piece(self):
        """Should detect A major from a simple A major piece."""
        notes = [mp.note('A', 4), mp.note('C#', 5), mp.note('E', 5),
                 mp.note('D', 5), mp.note('C#', 5), mp.note('B', 4), mp.note('A', 4)]
        track = mp.chord(notes, interval=[0.0] + [0.5] * 6)
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)
        result, info = extract_melody_pipeline(piece, return_info=True)
        assert 'key' in info
        # Should contain A major or F# minor
        assert 'A' in info['key'] or 'F#' in info['key']

    def test_handles_empty_piece(self):
        piece = mp.P(tracks=[], instruments=[], start_times=[], bpm=120)
        result = extract_melody_pipeline(piece)
        assert len(result.tracks) == 0

    def test_output_is_single_track(self, simple_melody_piece):
        result = extract_melody_pipeline(simple_melody_piece)
        assert len(result.tracks) == 1

    def test_velocities_normalized(self, simple_melody_piece):
        result = extract_melody_pipeline(simple_melody_piece)
        for track in result.tracks:
            for note in (track.notes if hasattr(track, 'notes') else list(track)):
                if hasattr(note, 'volume'):
                    assert 40 <= note.volume <= 110
