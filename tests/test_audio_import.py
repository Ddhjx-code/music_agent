"""
Tests for core/audio_import.py.

Uses mocked subprocess calls and module imports since we don't
want to actually run demucs/basic_pitch/ffmpeg in unit tests.
"""

import os
import subprocess
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from core.audio_import import (
    check_audio_import_deps, audio_to_wav, separate_stems,
    wav_to_midi, wav_to_midi_basic_pitch, wav_to_midi_omniaudio,
    separate_and_transcribe, merge_midi_files, import_audio, _find_executable,
)


class TestCheckAudioImportDeps:
    """Test dependency checking."""

    def test_returns_dict_with_expected_keys(self):
        """Should return dict with demucs, basic_pitch, and omniaudio keys."""
        result = check_audio_import_deps()
        assert 'demucs' in result
        assert 'basic_pitch' in result
        assert 'omniaudio' in result
        assert isinstance(result['demucs'], bool)
        assert isinstance(result['basic_pitch'], bool)
        assert isinstance(result['omniaudio'], bool)


class TestAudioToWav:
    """Test WAV conversion with mocked ffmpeg."""

    @patch('core.audio_import.subprocess.run')
    @patch('core.audio_import.os.path.exists')
    @patch('core.audio_import._find_executable')
    def test_converts_mp3_to_wav(self, mock_find, mock_exists, mock_run, tmp_path):
        """Should convert MP3 to WAV via ffmpeg."""
        mock_find.return_value = '/usr/bin/ffmpeg'
        mock_run.return_value = MagicMock(returncode=0, stderr='')
        mock_exists.return_value = True

        mp3_path = str(tmp_path / 'input.mp3')
        wav_path = str(tmp_path / 'output.wav')

        result = audio_to_wav(mp3_path, wav_path)
        assert result == wav_path
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert 'ffmpeg' in call_args
        assert '-ar' in call_args
        assert '44100' in call_args
        assert '-ac' in call_args
        assert '1' in call_args

    @patch('core.audio_import.shutil')
    def test_copies_wav_without_conversion(self, mock_shutil, tmp_path):
        """Should copy WAV files directly without ffmpeg."""
        # Create fake input file
        wav_input = str(tmp_path / 'input.wav')
        wav_output = str(tmp_path / 'output.wav')
        (tmp_path / 'input.wav').touch()

        result = audio_to_wav(wav_input, wav_output)
        assert result == wav_output
        mock_shutil.copy2.assert_called_once()

    @patch('core.audio_import._find_executable')
    def test_returns_none_when_ffmpeg_missing(self, mock_find, tmp_path):
        """Should return None when ffmpeg is not available."""
        mock_find.return_value = None

        mp3_path = str(tmp_path / 'input.mp3')
        wav_path = str(tmp_path / 'output.wav')

        result = audio_to_wav(mp3_path, wav_path)
        assert result is None

    @patch('core.audio_import.subprocess.run')
    @patch('core.audio_import._find_executable')
    def test_returns_none_on_ffmpeg_error(self, mock_find, mock_run, tmp_path):
        """Should return None when ffmpeg fails."""
        mock_find.return_value = '/usr/bin/ffmpeg'
        mock_run.return_value = MagicMock(returncode=1, stderr='ffmpeg error')

        mp3_path = str(tmp_path / 'input.mp3')
        wav_path = str(tmp_path / 'output.wav')

        with patch('core.audio_import.os.path.exists', return_value=False):
            result = audio_to_wav(mp3_path, wav_path)
        assert result is None

    @patch('core.audio_import.subprocess.run')
    @patch('core.audio_import._find_executable')
    def test_returns_none_on_file_not_found(self, mock_find, mock_run, tmp_path):
        """Should return None when ffmpeg binary not found at runtime."""
        mock_find.return_value = '/usr/bin/ffmpeg'
        mock_run.side_effect = FileNotFoundError()

        mp3_path = str(tmp_path / 'input.mp3')
        wav_path = str(tmp_path / 'output.wav')

        result = audio_to_wav(mp3_path, wav_path)
        assert result is None

    @patch('core.audio_import.subprocess.run')
    @patch('core.audio_import._find_executable')
    def test_returns_none_on_timeout(self, mock_find, mock_run, tmp_path):
        """Should return None when ffmpeg times out."""
        mock_find.return_value = '/usr/bin/ffmpeg'
        mock_run.side_effect = subprocess.TimeoutExpired('ffmpeg', 120)

        mp3_path = str(tmp_path / 'input.mp3')
        wav_path = str(tmp_path / 'output.wav')

        result = audio_to_wav(mp3_path, wav_path)
        assert result is None


class TestSeparateStems:
    """Test stem separation with mocked demucs."""

    @patch('core.audio_import.check_audio_import_deps')
    def test_returns_none_when_demucs_missing(self, mock_deps):
        """Should return None when demucs is not installed."""
        mock_deps.return_value = {'demucs': False, 'basic_pitch': False, 'omniaudio': False}

        result = separate_stems('input.wav', '/tmp/output')
        assert result is None


class TestWavToMidi:
    """Test MIDI transcription with mocked basic_pitch."""

    @patch('core.audio_import.check_audio_import_deps')
    def test_returns_none_when_basic_pitch_missing(self, mock_deps):
        """Should return None when basic_pitch is not installed."""
        mock_deps.return_value = {'demucs': False, 'basic_pitch': False, 'omniaudio': False}

        result = wav_to_midi('input.wav', 'output.mid')
        assert result is None


class TestImportAudio:
    """Test full audio import pipeline."""

    def test_returns_none_when_file_not_found(self):
        """Should return None when input audio doesn't exist."""
        result = import_audio('nonexistent.mp3')
        assert result is None

    @patch('core.audio_import.audio_to_wav')
    @patch('core.audio_import.separate_stems')
    @patch('core.audio_import.wav_to_midi')
    @patch('core.audio_import.os.path.getsize')
    @patch('core.audio_import.os.path.exists')
    def test_full_pipeline_with_stem_separation(
        self, mock_exists, mock_getsize, mock_wav_to_midi, mock_separate, mock_audio_to_wav, tmp_path
    ):
        """Should run full pipeline: convert → separate → transcribe."""
        midi_path = str(tmp_path / 'output.mid')
        mock_audio_to_wav.return_value = str(tmp_path / 'converted.wav')
        mock_separate.return_value = [str(tmp_path / 'vocals.wav')]
        mock_wav_to_midi.return_value = midi_path
        mock_exists.return_value = True
        mock_getsize.return_value = 1000

        # Create fake input file
        input_path = str(tmp_path / 'input.mp3')
        (tmp_path / 'input.mp3').touch()

        result = import_audio(input_path, midi_path, separate=True)
        assert result == midi_path
        mock_audio_to_wav.assert_called_once()
        mock_separate.assert_called_once()
        mock_wav_to_midi.assert_called_once()

    @patch('core.audio_import.audio_to_wav')
    @patch('core.audio_import.wav_to_midi')
    @patch('core.audio_import.os.path.getsize')
    @patch('core.audio_import.os.path.exists')
    def test_pipeline_skips_separation_when_disabled(
        self, mock_exists, mock_getsize, mock_wav_to_midi, mock_audio_to_wav, tmp_path
    ):
        """Should skip stem separation when separate=False."""
        midi_path = str(tmp_path / 'output.mid')
        mock_audio_to_wav.return_value = str(tmp_path / 'converted.wav')
        mock_wav_to_midi.return_value = midi_path
        mock_exists.return_value = True
        mock_getsize.return_value = 1000

        input_path = str(tmp_path / 'input.mp3')
        (tmp_path / 'input.mp3').touch()

        result = import_audio(input_path, midi_path, separate=False)
        assert result == midi_path
        mock_audio_to_wav.assert_called_once()
        mock_wav_to_midi.assert_called_once()

    @patch('core.audio_import.audio_to_wav')
    def test_pipeline_aborts_when_conversion_fails(self, mock_audio_to_wav, tmp_path):
        """Should abort pipeline when WAV conversion fails."""
        mock_audio_to_wav.return_value = None

        input_path = str(tmp_path / 'input.mp3')
        (tmp_path / 'input.mp3').touch()

        result = import_audio(input_path, separate=False)
        assert result is None


class TestFindExecutable:
    """Test executable finder."""

    def test_finds_known_executable(self):
        """Should find executables that exist in PATH."""
        result = _find_executable('python3')
        assert result is not None

    def test_returns_none_for_missing_executable(self):
        """Should return None for non-existent executables."""
        result = _find_executable('definitely_not_a_real_executable_xyz')
        assert result is None


class TestOmniAudioTranscription:
    """Test OmniAudio engine integration."""

    @patch('core.audio_import.check_audio_import_deps')
    def test_returns_none_when_omniaudio_missing(self, mock_deps):
        """Should return None when omniaudio is not installed."""
        mock_deps.return_value = {'demucs': False, 'basic_pitch': False, 'omniaudio': False}
        result = wav_to_midi('input.wav', 'output.mid', engine='omniaudio')
        assert result is None

    @patch('core.audio_import.check_audio_import_deps')
    def test_wav_to_midi_with_basic_pitch_fallback(self, mock_deps):
        """Should fall back to basic_pitch when omniaudio unavailable."""
        mock_deps.return_value = {'demucs': False, 'basic_pitch': True, 'omniaudio': False}
        with patch('core.audio_import.wav_to_midi_basic_pitch', return_value='output.mid') as mock_bp:
            result = wav_to_midi('input.wav', 'output.mid', engine='omniaudio')
            assert result == 'output.mid'
            mock_bp.assert_called_once()


class TestWavToMidiPostprocess:
    """Test post-processing integration."""

    @patch('core.audio_import._postprocess_midi')
    @patch('core.audio_import.wav_to_midi_omniaudio')
    @patch('core.audio_import.check_audio_import_deps')
    @patch('core.audio_import.os.path.exists')
    @patch('core.audio_import.os.path.getsize')
    def test_runs_postprocess_when_enabled(self, mock_getsize, mock_exists, mock_deps, mock_omni, mock_pp, tmp_path):
        """Should run post-processing when enabled and available."""
        mock_deps.return_value = {'omniaudio': True, 'basic_pitch': False}
        mock_omni.return_value = str(tmp_path / 'output.mid')
        mock_exists.return_value = True
        mock_getsize.return_value = 1000

        import musicpy as mp
        piece = mp.P(tracks=[], instruments=[], start_times=[], bpm=120)

        with patch('musicpy.read', return_value=piece):
            with patch('musicpy.write'):
                result = wav_to_midi(str(tmp_path / 'input.wav'), str(tmp_path / 'output.mid'), postprocess=True)
                assert result == str(tmp_path / 'output.mid')
                mock_pp.assert_called_once()

    @patch('core.audio_import.wav_to_midi_omniaudio')
    @patch('core.audio_import.check_audio_import_deps')
    @patch('core.audio_import.os.path.exists')
    @patch('core.audio_import.os.path.getsize')
    def test_skips_postprocess_when_disabled(self, mock_getsize, mock_exists, mock_deps, mock_omni, tmp_path):
        """Should skip post-processing when disabled."""
        mock_deps.return_value = {'omniaudio': True, 'basic_pitch': False}
        mock_omni.return_value = str(tmp_path / 'output.mid')
        mock_exists.return_value = True
        mock_getsize.return_value = 1000

        import musicpy as mp
        piece = mp.P(tracks=[], instruments=[], start_times=[], bpm=120)

        with patch('core.audio_import._postprocess_midi') as mock_pp:
            with patch('musicpy.read', return_value=piece):
                with patch('musicpy.write'):
                    result = wav_to_midi(str(tmp_path / 'input.wav'), str(tmp_path / 'output.mid'), postprocess=False)
                    assert result == str(tmp_path / 'output.mid')
                    mock_pp.assert_not_called()


class TestSeparateAndTranscribe:
    """Test stem-based transcription pipeline."""

    @patch('core.audio_import.separate_stems')
    @patch('core.audio_import.wav_to_midi')
    @patch('core.audio_import.os.path.exists')
    @patch('core.audio_import.os.path.getsize')
    def test_transcribes_each_stem_separately(self, mock_getsize, mock_exists,
                                               mock_wav_to_midi, mock_separate, tmp_path):
        """Should transcribe each stem and merge results."""
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

        (tmp_path / 'vocals.wav').touch()
        (tmp_path / 'bass.wav').touch()

        with patch('core.audio_import.merge_midi_files', return_value=str(tmp_path / 'merged.mid')):
            result = separate_and_transcribe(
                str(tmp_path / 'input.wav'),
                str(tmp_path / 'output'),
                engine='omniaudio'
            )
            assert result is not None
            assert mock_wav_to_midi.call_count == 2

    @patch('core.audio_import.separate_stems')
    def test_falls_back_to_full_file_when_demucs_fails(self, mock_separate):
        """Should use full file when stem separation fails."""
        mock_separate.return_value = None
        with patch('core.audio_import.wav_to_midi') as mock_wav_to_midi:
            mock_wav_to_midi.return_value = 'output.mid'
            result = separate_and_transcribe('input.wav', 'output')
            assert result == 'output.mid'
            mock_wav_to_midi.assert_called_once()


class TestMergeMidiFiles:
    """Test MIDI merging."""

    @patch('musicpy.read')
    @patch('musicpy.write')
    def test_merges_multiple_midis(self, mock_write, mock_read, tmp_path):
        """Should merge multiple MIDI files into one."""
        import musicpy as mp
        track1 = mp.chord([mp.note('C', 4, duration=0.25)], interval=[0.0])
        track2 = mp.chord([mp.note('E', 3, duration=0.25)], interval=[0.0])
        piece1 = mp.P(tracks=[track1], instruments=[1], start_times=[0], bpm=120)
        piece2 = mp.P(tracks=[track2], instruments=[33], start_times=[0], bpm=120)
        mock_read.side_effect = [piece1, piece2]

        stem_midis = [('vocals', 'v.mid'), ('bass', 'b.mid')]
        output_path = str(tmp_path / 'merged.mid')
        result = merge_midi_files(stem_midis, output_path)
        assert result == output_path
        mock_write.assert_called_once()
        merged_piece = mock_write.call_args[0][0]
        assert len(merged_piece.tracks) == 2
        assert merged_piece.instruments == [1, 33]
