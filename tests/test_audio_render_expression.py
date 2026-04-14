"""Tests for core/audio_render_expression.py."""

import musicpy as mp
import pytest

from core.audio_render_expression import (
    apply_velocity_mapping, apply_phrase_expression, apply_rubato,
    apply_full_expression
)


class TestApplyVelocityMapping:
    """Test velocity mapping by voice role."""

    def test_melody_gets_higher_velocity(self, simple_melody_piece):
        """Melody track should get 70-110 velocity range."""
        for track in simple_melody_piece.tracks:
            for note in (track.notes if hasattr(track, 'notes') else list(track)):
                note.volume = 60

        result = apply_velocity_mapping(simple_melody_piece, profile='piano')
        melody_velocities = [
            n.volume for n in result.tracks[0]
            if hasattr(n, 'volume')
        ]
        assert all(70 <= v <= 110 for v in melody_velocities), \
            f"Melody velocities: {melody_velocities}"

    def test_accompaniment_gets_lower_velocity(self, simple_melody_piece):
        """Accompaniment track should get 40-70 velocity range."""
        for track in simple_melody_piece.tracks:
            for note in (track.notes if hasattr(track, 'notes') else list(track)):
                note.volume = 60

        result = apply_velocity_mapping(simple_melody_piece, profile='piano')
        accomp_velocities = [
            n.volume for n in result.tracks[1]
            if hasattr(n, 'volume')
        ]
        assert all(40 <= v <= 70 for v in accomp_velocities), \
            f"Accompaniment velocities: {accomp_velocities}"

    def test_empty_piece_returns_unchanged(self):
        """Empty piece should return unchanged."""
        piece = mp.P(tracks=[], instruments=[], start_times=[], bpm=120)
        result = apply_velocity_mapping(piece)
        assert result is piece


class TestApplyPhraseExpression:
    """Test phrase-based expression."""

    def test_adds_crescendo_to_phrase(self):
        """Notes in a phrase should get crescendo pattern."""
        notes = [mp.note('C', 4, duration=0.25) for _ in range(4)]
        notes[0].volume = 60
        track = mp.chord(notes, interval=[0.0] + [0.25] * 3)
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)

        result = apply_phrase_expression(piece, phrase_length=4)
        velocities = [n.volume for n in result.tracks[0]]
        assert velocities[-1] > velocities[0]

    def test_empty_piece_returns_unchanged(self):
        piece = mp.P(tracks=[], instruments=[], start_times=[], bpm=120)
        result = apply_phrase_expression(piece)
        assert result is piece


class TestApplyRubato:
    """Test rubato timing variation."""

    def test_adds_timing_variation(self):
        """Notes should get small timing offsets."""
        notes = [mp.note('C', 4, duration=0.25) for _ in range(8)]
        track = mp.chord(notes, interval=[0.0] + [0.25] * 7)
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)

        result = apply_rubato(piece, amount=0.02, seed=42)
        intervals = getattr(result.tracks[0], 'interval', [])
        varied = [iv for iv in intervals[1:] if abs(iv - 0.25) > 0.001]
        assert len(varied) > 0, "No timing variation applied"

    def test_respects_amount_parameter(self):
        """Larger amount should produce larger variations."""
        notes = [mp.note('C', 4, duration=0.25) for _ in range(8)]
        track = mp.chord(notes, interval=[0.0] + [0.25] * 7)
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)

        result_small = apply_rubato(piece, amount=0.005, seed=42)
        result_large = apply_rubato(piece, amount=0.05, seed=42)

        small_devs = [abs(iv - 0.25) for iv in getattr(result_small.tracks[0], 'interval', [])[1:]]
        large_devs = [abs(iv - 0.25) for iv in getattr(result_large.tracks[0], 'interval', [])[1:]]
        assert max(large_devs) > max(small_devs)

    def test_empty_piece_returns_unchanged(self):
        piece = mp.P(tracks=[], instruments=[], start_times=[], bpm=120)
        result = apply_rubato(piece)
        assert result is piece


class TestApplyFullExpression:
    """Test full expression pipeline."""

    def test_applies_all_steps(self, simple_melody_piece):
        """Should apply velocity mapping + phrase + rubato."""
        for track in simple_melody_piece.tracks:
            for note in (track.notes if hasattr(track, 'notes') else list(track)):
                note.volume = 60

        result = apply_full_expression(
            simple_melody_piece,
            profile='piano',
            phrase_length=4,
            rubato_amount=0.01
        )

        assert len(result.tracks) == len(simple_melody_piece.tracks)
        melody_vel = [n.volume for n in result.tracks[0] if hasattr(n, 'volume')]
        assert any(v >= 70 for v in melody_vel)
