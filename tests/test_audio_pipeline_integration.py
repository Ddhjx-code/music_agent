"""Integration tests for the full audio pipeline: WAV -> MIDI -> WAV."""

import os
from unittest.mock import patch, MagicMock

import pytest
import musicpy as mp

from core.audio_import import wav_to_midi, separate_and_transcribe
from core.audio_render import render_audio, render_timidity
from core.audio_render_expression import apply_full_expression
from core.audio_postprocess import postprocess_midi


class TestFullAudioRoundTrip:
    """Test full WAV -> MIDI -> WAV round-trip with mocked engines."""

    @patch('core.audio_import.wav_to_midi_omniaudio')
    @patch('core.audio_import.check_audio_import_deps')
    @patch('core.audio_import.os.path.exists')
    @patch('core.audio_import.os.path.getsize')
    @patch('core.audio_render.render_wav')
    def test_wav_to_mid_to_wav(self, mock_render_wav, mock_getsize,
                                mock_exists, mock_deps, mock_omni, tmp_path):
        """Full pipeline: WAV -> MIDI -> WAV should produce output."""
        mock_deps.return_value = {'omniaudio': True, 'basic_pitch': False}
        mock_omni.return_value = str(tmp_path / 'output.mid')
        mock_exists.return_value = True
        mock_getsize.return_value = 1000

        track = mp.chord([mp.note('C', 4, duration=0.25)], interval=[0.0])
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)

        with patch('musicpy.read', return_value=piece):
            with patch('core.audio_import._postprocess_midi', return_value=piece):
                with patch('musicpy.write'):
                    midi_result = wav_to_midi(
                        str(tmp_path / 'input.wav'),
                        str(tmp_path / 'output.mid'),
                        engine='omniaudio',
                        postprocess=True
                    )
                    assert midi_result is not None

        mock_render_wav.return_value = str(tmp_path / 'rendered.wav')
        wav_result = render_audio(
            str(tmp_path / 'output.mid'),
            str(tmp_path / 'rendered.wav'),
            engine='fluidsynth',
        )
        assert wav_result is not None


class TestPerStemTranscriptionIntegration:
    """Test per-stem transcription with merging."""

    @patch('core.audio_import.merge_midi_files')
    @patch('core.audio_import.wav_to_midi')
    @patch('core.audio_import.separate_stems')
    @patch('core.audio_import.check_audio_import_deps')
    @patch('core.audio_import.os.path.exists')
    @patch('core.audio_import.os.path.getsize')
    def test_separate_and_transcribe_with_stems(self, mock_getsize, mock_exists,
                                                  mock_deps, mock_separate,
                                                  mock_wav_to_midi, mock_merge, tmp_path):
        """Should separate, transcribe stems, and merge."""
        mock_deps.return_value = {'omniaudio': True, 'demucs': True}
        (tmp_path / 'vocals.wav').touch()
        (tmp_path / 'bass.wav').touch()
        mock_separate.return_value = [
            str(tmp_path / 'vocals.wav'),
            str(tmp_path / 'bass.wav'),
        ]
        mock_wav_to_midi.side_effect = [
            str(tmp_path / 'vocals.mid'),
            str(tmp_path / 'bass.mid'),
        ]
        mock_exists.return_value = True
        mock_getsize.return_value = 1000
        mock_merge.return_value = str(tmp_path / 'merged.mid')

        (tmp_path / 'input.wav').touch()

        result = separate_and_transcribe(
            str(tmp_path / 'input.wav'),
            str(tmp_path / 'output'),
        )
        assert result == str(tmp_path / 'merged.mid')
        assert mock_wav_to_midi.call_count == 2
        mock_merge.assert_called_once()


class TestExpressionBeforeRender:
    """Test expression pre-processing before rendering."""

    def test_expression_improves_velocity_contrast(self, simple_melody_piece, tmp_path):
        """Expression should create clearer melody/accompaniment contrast."""
        for track in simple_melody_piece.tracks:
            for note in (track.notes if hasattr(track, 'notes') else list(track)):
                note.volume = 60

        result = apply_full_expression(simple_melody_piece, profile='piano')

        melody_vel = [n.volume for n in result.tracks[0] if hasattr(n, 'volume')]
        accomp_vel = [n.volume for n in result.tracks[1] if hasattr(n, 'volume')]

        melody_avg = sum(melody_vel) / max(1, len(melody_vel))
        accomp_avg = sum(accomp_vel) / max(1, len(accomp_vel))

        assert melody_avg > accomp_avg + 8, \
            f"Melody avg: {melody_avg}, Accomp avg: {accomp_avg}"


class TestPostprocessThenRender:
    """Test that postprocessed MIDI can be used in render pipeline."""

    @patch('core.audio_render.render_wav')
    def test_postprocessed_midi_renders(self, mock_render_wav, simple_melody_piece, tmp_path):
        """Postprocessed piece should render without errors."""
        postprocessed = postprocess_midi(simple_melody_piece)

        midi_path = str(tmp_path / 'processed.mid')
        import musicpy as mp
        mp.write(postprocessed, name=midi_path)

        mock_render_wav.return_value = str(tmp_path / 'output.wav')

        result = render_audio(midi_path, str(tmp_path / 'output.wav'))
        assert result is not None


class TestRenderEngineSelection:
    """Test that render_audio correctly selects engine."""

    @patch('core.audio_render.render_timidity')
    def test_uses_timidity_when_requested(self, mock_timidity, tmp_path):
        """Should route to timidity when engine='timidity'."""
        mock_timidity.return_value = str(tmp_path / 'output.wav')
        (tmp_path / 'input.mid').touch()

        with patch('core.audio_render.discover_soundfont', return_value=None):
            result = render_audio(
                str(tmp_path / 'input.mid'),
                str(tmp_path / 'output.wav'),
                engine='timidity',
            )
        assert result == str(tmp_path / 'output.wav')
        mock_timidity.assert_called_once()

    @patch('core.audio_render.render_wav')
    def test_uses_fluidsynth_by_default(self, mock_render_wav, tmp_path):
        """Should route to fluidsynth by default."""
        mock_render_wav.return_value = str(tmp_path / 'output.wav')
        (tmp_path / 'input.mid').touch()

        with patch('core.audio_render.discover_soundfont', return_value=str(tmp_path / 'test.sf2')):
            result = render_audio(
                str(tmp_path / 'input.mid'),
                str(tmp_path / 'output.wav'),
                engine='fluidsynth',
            )
        assert result == str(tmp_path / 'output.wav')
        mock_render_wav.assert_called_once()
