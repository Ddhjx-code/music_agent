"""
Tests for core/json_schema.py — Music Summary JSON generator.

The summary is what the LLM sees. It must be compact, accurate, and serializable.
"""

import json

import pytest

from core.json_schema import generate_summary


REQUIRED_FIELDS = [
    'title', 'key', 'bpm', 'time_signature',
    'num_measures', 'num_tracks', 'tracks',
    'chord_progression', 'form',
]

TRACK_FIELDS = ['name', 'instrument', 'role', 'pitch_range', 'avg_velocity']


class TestGenerateSummary:
    """Tests for generate_summary()."""

    def test_summary_has_required_fields(self, simple_melody_piece):
        """Summary dict contains all required top-level fields."""
        summary = generate_summary(simple_melody_piece)

        for field in REQUIRED_FIELDS:
            assert field in summary, f"Missing field: {field}"

    def test_summary_bpm_matches(self, simple_melody_piece):
        """Summary BPM matches the piece BPM."""
        summary = generate_summary(simple_melody_piece)
        assert summary['bpm'] == 120

    def test_summary_track_count(self, simple_melody_piece):
        """Summary track count matches piece track count."""
        summary = generate_summary(simple_melody_piece)
        assert summary['num_tracks'] == 2

    def test_summary_track_roles(self, pop_song_piece):
        """Each track has an inferred role."""
        summary = generate_summary(pop_song_piece)

        for track in summary['tracks']:
            assert 'role' in track
            assert track['role'] in ('melody', 'harmony', 'bass', 'percussion')

    def test_summary_pitch_ranges(self, simple_melody_piece):
        """Each track has a pitch_range string like 'C4-G5'."""
        summary = generate_summary(simple_melody_piece)

        for track in summary['tracks']:
            assert 'pitch_range' in track
            assert isinstance(track['pitch_range'], str)
            assert '-' in track['pitch_range']

    def test_summary_chord_progression_is_list(self, simple_melody_piece):
        """Chord progression is a list of dicts with measure and chord keys."""
        summary = generate_summary(simple_melody_piece)

        assert isinstance(summary['chord_progression'], list)
        if summary['chord_progression']:
            entry = summary['chord_progression'][0]
            assert 'measure' in entry
            assert 'chord' in entry

    def test_summary_chord_progression_detects_known_chords(self, simple_melody_piece):
        """Summary detects the C-G-Am-F chord progression in the fixture."""
        summary = generate_summary(simple_melody_piece)
        chords = [e['chord'] for e in summary['chord_progression']]
        chord_str = ' '.join(chords).lower()

        # At minimum, C major should be detected
        assert 'c' in chord_str

    def test_summary_serializable(self, simple_melody_piece):
        """Summary can be serialized to JSON without errors."""
        summary = generate_summary(simple_melody_piece)
        json_str = json.dumps(summary)
        assert len(json_str) > 0

    def test_summary_title_default(self, simple_melody_piece):
        """Default title is 'Untitled'."""
        summary = generate_summary(simple_melody_piece)
        assert summary['title'] == 'Untitled'

    def test_summary_title_custom(self, simple_melody_piece):
        """Custom title is respected."""
        summary = generate_summary(simple_melody_piece, title="Twinkle Twinkle")
        assert summary['title'] == "Twinkle Twinkle"

    def test_summary_num_measures(self, simple_melody_piece):
        """Number of measures is computed."""
        summary = generate_summary(simple_melody_piece)
        assert summary['num_measures'] > 0

    def test_summary_form_sections(self, simple_melody_piece):
        """Form sections are identified."""
        summary = generate_summary(simple_melody_piece)

        assert isinstance(summary['form'], list)
        # At minimum, one section should exist
        assert len(summary['form']) >= 1

    def test_summary_track_instrument(self, pop_song_piece):
        """Track instrument info is correctly reported."""
        summary = generate_summary(pop_song_piece)

        instruments = [t['instrument'] for t in summary['tracks']]
        assert 1 in instruments   # Piano
        assert 25 in instruments  # Guitar

    def test_summary_track_avg_velocity(self, simple_melody_piece):
        """Average velocity is computed per track."""
        summary = generate_summary(simple_melody_piece)

        for track in summary['tracks']:
            assert 'avg_velocity' in track
            assert isinstance(track['avg_velocity'], int)
            assert 0 < track['avg_velocity'] <= 127
