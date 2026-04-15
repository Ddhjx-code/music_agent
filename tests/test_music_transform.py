"""Tests for music_transform module — piece ↔ JSON bidirectional conversion."""

import json
import pytest
import musicpy as mp

from core.music_transform import piece_to_json, json_to_piece


class TestPieceToJSON:
    """Test piece_to_json conversion."""

    def test_basic_structure(self, simple_melody_piece):
        """JSON should contain summary + tracks + notes."""
        result = piece_to_json(simple_melody_piece)
        assert 'summary' in result
        assert 'tracks' in result
        assert result['summary']['bpm'] == 120
        assert result['summary']['num_tracks'] == 2

    def test_track_note_data(self, simple_melody_piece):
        """Each track should have full note data (pitch, duration, velocity, start_time)."""
        result = piece_to_json(simple_melody_piece)
        for track in result['tracks']:
            assert 'notes' in track
            for note in track['notes']:
                assert 'pitch' in note
                assert 'duration' in note
                assert 'velocity' in note
                assert 'start_time' in note

    def test_harmony_included(self, simple_melody_piece):
        """JSON should include chord progression."""
        result = piece_to_json(simple_melody_piece)
        assert 'chord_progression' in result['summary']
        assert len(result['summary']['chord_progression']) > 0


class TestJSONToPiece:
    """Test json_to_piece round-trip."""

    def test_round_trip_preserves_notes(self, simple_melody_piece):
        """piece → JSON → piece should preserve note count and pitches."""
        original_degrees = sorted(
            n.degree for t in simple_melody_piece.tracks for n in t if hasattr(n, 'degree')
        )
        json_data = piece_to_json(simple_melody_piece)
        restored = json_to_piece(json_data)
        restored_degrees = sorted(
            n.degree for t in restored.tracks for n in t if hasattr(n, 'degree')
        )
        assert len(original_degrees) == len(restored_degrees)
        assert original_degrees == restored_degrees

    def test_round_trip_preserves_bpm(self, simple_melody_piece):
        """BPM should be preserved through round-trip."""
        json_data = piece_to_json(simple_melody_piece)
        restored = json_to_piece(json_data)
        assert restored.bpm == simple_melody_piece.bpm


class TestLLMFriendlyFormat:
    """Test that JSON is usable by LLM."""

    def test_readable_summary(self, simple_melody_piece):
        """Summary section should be human/LLM readable."""
        result = piece_to_json(simple_melody_piece)
        summary = result['summary']
        assert 'key' in summary
        assert 'time_signature' in summary
        assert 'form' in summary

    def test_json_serializable(self, simple_melody_piece):
        """Output must be pure JSON-serializable data (no musicpy objects)."""
        result = piece_to_json(simple_melody_piece)
        # Should not raise
        json.dumps(result)
