"""
Tests for core/audio_render.py.

Uses mocked subprocess calls since we don't want to actually
run fluidsynth/ffmpeg in unit tests.
"""

import os
from unittest.mock import patch, MagicMock

import pytest

from core.audio_render import (
    discover_soundfont, render_wav, render_mp3, render_audio,
    SOUNDFONT_CANDIDATES,
)


class TestDiscoverSoundfont:
    """Test SoundFont auto-discovery."""

    def test_returns_none_when_no_files_exist(self, tmp_path):
        """Should return None when no candidates exist."""
        candidates = [str(tmp_path / 'nonexistent.sf2')]
        result = discover_soundfont(candidates)
        assert result is None

    def test_returns_first_existing_file(self, tmp_path):
        """Should return the first existing file from candidates."""
        sf2_path = tmp_path / 'test.sf2'
        sf2_path.touch()
        candidates = [str(tmp_path / 'missing.sf2'), str(sf2_path)]
        result = discover_soundfont(candidates)
        assert result == str(sf2_path)

    def test_respects_custom_paths(self, tmp_path):
        """Should use custom paths over defaults."""
        custom_sf2 = tmp_path / 'custom.sf2'
        custom_sf2.touch()
        result = discover_soundfont([str(custom_sf2)])
        assert result == str(custom_sf2)


class TestRenderWav:
    """Test WAV rendering with mocked fluidsynth."""

    @patch('core.audio_render.subprocess.run')
    @patch('core.audio_render.os.path.exists')
    @patch('core.audio_render.open')
    @patch('core.audio_render.wave.open')
    @patch('core.audio_render.os.remove')
    def test_success(self, mock_remove, mock_wave_open, mock_open,
                     mock_exists, mock_run, tmp_path):
        """Should render WAV on successful fluidsynth run."""
        mock_run.return_value = MagicMock(returncode=0, stderr='')
        mock_exists.return_value = True
        mock_exists.side_effect = lambda p: p.endswith('.raw')
        mock_open.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        mock_wave_open.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_wave_open.return_value.__exit__ = MagicMock(return_value=False)

        midi_path = str(tmp_path / 'input.mid')
        wav_path = str(tmp_path / 'output.wav')
        sf2_path = str(tmp_path / 'test.sf2')

        result = render_wav(midi_path, wav_path, sf2_path)
        assert result == wav_path
        mock_run.assert_called_once()

    @patch('core.audio_render.subprocess.run')
    def test_fluidsynth_not_found(self, mock_run, tmp_path):
        """Should return None with clear error when fluidsynth missing."""
        mock_run.side_effect = FileNotFoundError()

        midi_path = str(tmp_path / 'input.mid')
        wav_path = str(tmp_path / 'output.wav')
        sf2_path = str(tmp_path / 'test.sf2')

        result = render_wav(midi_path, wav_path, sf2_path)
        assert result is None


class TestRenderMp3:
    """Test MP3 rendering."""

    @patch('core.audio_render.render_wav')
    @patch('core.audio_render.subprocess.run')
    @patch('core.audio_render.os.path.exists')
    @patch('core.audio_render.os.remove')
    def test_success(self, mock_remove, mock_exists, mock_ffmpeg_run,
                     mock_render_wav, tmp_path):
        """Should render MP3 via WAV intermediate."""
        wav_path = str(tmp_path / 'output.wav')
        mock_render_wav.return_value = wav_path
        mock_ffmpeg_run.return_value = MagicMock(returncode=0, stderr='')
        mock_exists.side_effect = lambda p: 'wav' in p or 'mid' in p

        midi_path = str(tmp_path / 'input.mid')
        mp3_path = str(tmp_path / 'output.mp3')
        sf2_path = str(tmp_path / 'test.sf2')

        result = render_mp3(midi_path, mp3_path, sf2_path)
        assert result == mp3_path
        mock_ffmpeg_run.assert_called_once()

    @patch('core.audio_render.render_wav')
    def test_fails_if_wav_render_fails(self, mock_render_wav, tmp_path):
        """Should return None if WAV rendering fails."""
        mock_render_wav.return_value = None

        midi_path = str(tmp_path / 'input.mid')
        mp3_path = str(tmp_path / 'output.mp3')
        sf2_path = str(tmp_path / 'test.sf2')

        result = render_mp3(midi_path, mp3_path, sf2_path)
        assert result is None

    @patch('core.audio_render.render_wav')
    @patch('core.audio_render.subprocess.run')
    def test_ffmpeg_not_found(self, mock_ffmpeg_run, mock_render_wav, tmp_path):
        """Should return None with clear error when ffmpeg missing."""
        wav_path = str(tmp_path / 'output.wav')
        mock_render_wav.return_value = wav_path
        mock_ffmpeg_run.side_effect = FileNotFoundError()

        midi_path = str(tmp_path / 'input.mid')
        mp3_path = str(tmp_path / 'output.mp3')
        sf2_path = str(tmp_path / 'test.sf2')

        result = render_mp3(midi_path, mp3_path, sf2_path)
        assert result is None


class TestRenderAudio:
    """Test unified render_audio entry point."""

    @patch('core.audio_render.render_wav')
    @patch('core.audio_render.discover_soundfont')
    def test_infers_wav_format(self, mock_discover, mock_render_wav, tmp_path):
        """Should infer WAV from .wav extension."""
        mock_discover.return_value = str(tmp_path / 'test.sf2')
        mock_render_wav.return_value = str(tmp_path / 'output.wav')

        result = render_audio(
            str(tmp_path / 'input.mid'),
            str(tmp_path / 'output.wav'),
        )
        assert result is not None
        mock_render_wav.assert_called_once()

    @patch('core.audio_render.render_wav')
    @patch('core.audio_render.discover_soundfont')
    @patch('core.audio_render.subprocess.run')
    @patch('core.audio_render.os.path.exists')
    @patch('core.audio_render.os.remove')
    def test_infers_mp3_format(self, mock_remove, mock_exists, mock_subprocess_run,
                                 mock_discover, mock_render_wav, tmp_path):
        """Should infer MP3 from .mp3 extension."""
        mock_discover.return_value = str(tmp_path / 'test.sf2')
        wav_path = str(tmp_path / 'output.wav')
        mock_render_wav.return_value = wav_path
        mock_subprocess_run.return_value = MagicMock(returncode=0, stderr='')
        mock_exists.side_effect = lambda p: 'wav' in p or 'mid' in p or 'sf2' in p

        result = render_audio(
            str(tmp_path / 'input.mid'),
            str(tmp_path / 'output.mp3'),
        )
        assert result is not None
        mock_render_wav.assert_called_once()

    @patch('core.audio_render.discover_soundfont')
    def test_returns_none_when_no_soundfont(self, mock_discover, tmp_path):
        """Should return None when no SoundFont found."""
        mock_discover.return_value = None

        result = render_audio(
            str(tmp_path / 'input.mid'),
            str(tmp_path / 'output.wav'),
        )
        assert result is None

    @patch('core.audio_render.render_wav')
    def test_respects_custom_sf2(self, mock_render_wav, tmp_path):
        """Should use provided SoundFont path."""
        sf2_path = str(tmp_path / 'custom.sf2')
        mock_render_wav.return_value = str(tmp_path / 'output.wav')

        render_audio(
            str(tmp_path / 'input.mid'),
            str(tmp_path / 'output.wav'),
            sf2_path=sf2_path,
        )
        # Verify sf2_path was passed through
        call_args = mock_render_wav.call_args
        assert call_args[0][2] == sf2_path


class TestRenderTimidity:
    """Test Timidity++ rendering."""

    @patch('core.audio_render.subprocess.run')
    @patch('core.audio_render.os.path.exists')
    def test_success(self, mock_exists, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr='')
        mock_exists.return_value = True
        midi_path = str(tmp_path / 'input.mid')
        wav_path = str(tmp_path / 'output.wav')

        from core.audio_render import render_timidity
        result = render_timidity(midi_path, wav_path)
        assert result == wav_path
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert 'timidity' in call_args

    @patch('core.audio_render.subprocess.run')
    def test_timidity_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        from core.audio_render import render_timidity
        result = render_timidity('input.mid', 'output.wav')
        assert result is None

    @patch('core.audio_render.subprocess.run')
    @patch('core.audio_render.os.path.exists')
    def test_reverb_chorus_options(self, mock_exists, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr='')
        mock_exists.return_value = True
        from core.audio_render import render_timidity
        render_timidity('input.mid', 'output.wav', reverb=True, chorus=True)
        call_args = mock_run.call_args[0][0]
        assert '-Or' in call_args
        assert '-Oc' in call_args


class TestRenderAudioPostfx:
    """Test audio post-processing effects."""

    @patch('core.audio_render.subprocess.run')
    @patch('core.audio_render.os.path.exists')
    def test_applies_reverb_via_ffmpeg(self, mock_exists, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr='')
        mock_exists.return_value = True
        input_wav = str(tmp_path / 'input.wav')
        output_wav = str(tmp_path / 'output.wav')

        from core.audio_render import apply_audio_postfx
        result = apply_audio_postfx(input_wav, output_wav, reverb=True)
        assert result == output_wav
        call_args = mock_run.call_args[0][0]
        assert 'ffmpeg' in call_args
        assert 'aecho' in ' '.join(call_args)

    @patch('core.audio_render.subprocess.run')
    @patch('core.audio_render.os.path.exists')
    def test_applies_normalization(self, mock_exists, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr='')
        mock_exists.return_value = True
        input_wav = str(tmp_path / 'input.wav')
        output_wav = str(tmp_path / 'output.wav')

        from core.audio_render import apply_audio_postfx
        result = apply_audio_postfx(input_wav, output_wav, normalize=True)
        assert result == output_wav

    @patch('core.audio_render.subprocess.run')
    @patch('core.audio_render.os.path.exists')
    def test_copies_when_no_fx(self, mock_exists, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr='')
        mock_exists.return_value = True
        input_wav = str(tmp_path / 'input.wav')
        output_wav = str(tmp_path / 'output.wav')

        import shutil
        with patch.object(shutil, 'copy2') as mock_copy:
            from core.audio_render import apply_audio_postfx
            result = apply_audio_postfx(input_wav, output_wav, reverb=False, compression=False, normalize=False)
            mock_copy.assert_called_once_with(input_wav, output_wav)


class TestRenderWavWithOptions:
    """Test render_wav with options dict."""

    @patch('core.audio_render.shutil.move')
    @patch('core.audio_render.apply_audio_postfx')
    @patch('core.audio_render.subprocess.run')
    @patch('core.audio_render.os.path.exists')
    @patch('core.audio_render.open')
    @patch('core.audio_render.wave.open')
    @patch('core.audio_render.os.remove')
    def test_applies_postfx_when_requested(self, mock_remove, mock_wave_open, mock_open,
                                            mock_exists, mock_subprocess_run, mock_postfx,
                                            mock_move):
        mock_subprocess_run.return_value = MagicMock(returncode=0, stderr='')
        mock_exists.side_effect = lambda p: 'raw' in p or 'wav' in p
        mock_postfx.return_value = '/tmp/output_postfx.wav'
        mock_open.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        mock_wave_open.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_wave_open.return_value.__exit__ = MagicMock(return_value=False)

        from core.audio_render import render_wav
        result = render_wav(
            'input.mid', 'output.wav', 'test.sf2',
            options={'postfx': {'reverb': True, 'normalize': True}}
        )
        assert result == 'output.wav'
        mock_postfx.assert_called_once()
        mock_move.assert_called_once()
