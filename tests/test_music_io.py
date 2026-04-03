"""
Tests for core/music_io.py — MIDI load/save round-trip and error handling.

TDD: These tests are written BEFORE the implementation.
"""

import os
import tempfile

import pytest
import musicpy as mp

from core.music_io import load_midi, save_midi, get_track_info


class TestLoadMidi:
    """Tests for load_midi()."""

    def test_load_returns_piece(self, simple_melody_piece, tmp_path):
        """Load a valid MIDI file returns a musicpy piece."""
        path = str(tmp_path / "test.mid")
        mp.write(simple_melody_piece, name=path)

        piece = load_midi(path)

        assert hasattr(piece, 'tracks')
        assert len(piece.tracks) == 2

    def test_load_preserves_bpm(self, simple_melody_piece, tmp_path):
        """Loaded piece has the same BPM as the original."""
        path = str(tmp_path / "test.mid")
        mp.write(simple_melody_piece, name=path)

        piece = load_midi(path)

        assert piece.bpm == 120

    def test_load_preserves_track_count(self, pop_song_piece, tmp_path):
        """Loaded piece has the same number of tracks."""
        path = str(tmp_path / "test.mid")
        mp.write(pop_song_piece, name=path)

        piece = load_midi(path)

        assert len(piece.tracks) == 3

    def test_load_invalid_path_raises(self):
        """Loading a non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_midi("/nonexistent/path/song.mid")

    def test_load_empty_file_raises(self, tmp_path):
        """Loading an empty file raises a clear error."""
        path = str(tmp_path / "empty.mid")
        with open(path, 'wb') as f:
            f.write(b'')

        with pytest.raises(ValueError):
            load_midi(path)


class TestSaveMidi:
    """Tests for save_midi()."""

    def test_save_creates_file(self, simple_melody_piece, tmp_path):
        """Save creates a MIDI file at the given path."""
        path = str(tmp_path / "output.mid")

        result = save_midi(simple_melody_piece, path)

        assert os.path.exists(path)
        assert result == path

    def test_save_creates_parent_dirs(self, simple_melody_piece, tmp_path):
        """Save creates parent directories if they don't exist."""
        path = str(tmp_path / "sub" / "dir" / "output.mid")

        result = save_midi(simple_melody_piece, path)

        assert os.path.exists(path)
        assert result == path

    def test_round_trip_preserves_tracks(self, simple_melody_piece, tmp_path):
        """Save then reload preserves track count and BPM."""
        path = str(tmp_path / "roundtrip.mid")
        save_midi(simple_melody_piece, path)

        reloaded = load_midi(path)

        assert len(reloaded.tracks) == len(simple_melody_piece.tracks)
        assert reloaded.bpm == simple_melody_piece.bpm

    def test_round_trip_preserves_note_count(self, single_track_piece, tmp_path):
        """Save then reload preserves the number of notes."""
        path = str(tmp_path / "notes.mid")
        original_note_count = sum(len(t) for t in single_track_piece.tracks)
        save_midi(single_track_piece, path)

        reloaded = load_midi(path)
        reloaded_note_count = sum(len(t) for t in reloaded.tracks)

        assert reloaded_note_count == original_note_count


class TestGetTrackInfo:
    """Tests for get_track_info()."""

    def test_returns_list_of_dicts(self, simple_melody_piece):
        """get_track_info returns a list of dicts, one per track."""
        info = get_track_info(simple_melody_piece)

        assert isinstance(info, list)
        assert len(info) == 2
        assert isinstance(info[0], dict)

    def test_track_has_required_fields(self, simple_melody_piece):
        """Each track info dict has name, instrument, channel, note_count."""
        info = get_track_info(simple_melody_piece)

        for track_info in info:
            assert 'note_count' in track_info
            assert 'instrument' in track_info
            assert isinstance(track_info['note_count'], int)
            assert track_info['note_count'] > 0

    def test_instrument_program_reported(self, pop_song_piece):
        """Instrument program number is correctly reported."""
        info = get_track_info(pop_song_piece)

        assert info[0]['instrument'] == 1    # Piano
        assert info[1]['instrument'] == 25   # Guitar
        assert info[2]['instrument'] == 33   # Bass

    def test_note_count_accurate(self, single_track_piece):
        """Note count matches actual note count."""
        info = get_track_info(single_track_piece)
        expected = sum(len(t) for t in single_track_piece.tracks)

        total = sum(t['note_count'] for t in info)
        assert total == expected
