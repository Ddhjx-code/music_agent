"""
Audio import module.

Pipeline: MP3/WAV → (Demucs stems) → Basic Pitch → MIDI → musicpy piece.

Gracefully handles missing optional dependencies with actionable error messages.
"""

import os
import shutil
import subprocess
import tempfile

# Lazy import for post-processing (used in wav_to_midi)
try:
    from core.audio_postprocess import (
        postprocess_midi as _postprocess_midi,
        extract_melody_pipeline as _extract_melody_pipeline,
    )
except ImportError:
    _postprocess_midi = None
    _extract_melody_pipeline = None


def check_audio_import_deps() -> dict[str, bool]:
    """Check availability of audio import dependencies."""
    result = {}
    for name in ['demucs', 'basic_pitch', 'omniaudio']:
        try:
            __import__(name)
            result[name] = True
        except ImportError:
            result[name] = False
    return result


def audio_to_wav(audio_path: str, wav_path: str) -> str | None:
    """
    Convert audio file to WAV (16-bit, 44100Hz, mono).

    If input is already WAV, copy it. Otherwise use ffmpeg.

    Args:
        audio_path: Input audio path (MP3, WAV, FLAC, OGG).
        wav_path: Output WAV path.

    Returns:
        Path to WAV file, or None on failure.
    """
    ext = os.path.splitext(audio_path)[1].lower()
    if ext == '.wav':
        # Already WAV — just copy
        shutil.copy2(audio_path, wav_path)
        return wav_path

    # Check ffmpeg
    if _find_executable('ffmpeg') is None:
        print("  Error: ffmpeg required for audio conversion.")
        print("  Install: brew install ffmpeg")
        return None

    try:
        result = subprocess.run(
            ['ffmpeg', '-y', '-i', audio_path, '-ar', '44100', '-ac', '1',
             '-sample_fmt', 's16', wav_path],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0 or not os.path.exists(wav_path):
            print(f"  Error: ffmpeg conversion failed: {result.stderr[:200]}")
            return None
        return wav_path
    except FileNotFoundError:
        print("  Error: ffmpeg not found.")
        return None
    except subprocess.TimeoutExpired:
        print("  Error: ffmpeg conversion timed out.")
        return None


def separate_stems(wav_path: str, output_dir: str,
                   model: str = 'htdemucs') -> list[str] | None:
    """
    Separate audio into stems using Demucs.

    Args:
        wav_path: Input WAV file.
        output_dir: Directory for output stems.
        model: Demucs model name (default: 'htdemucs').

    Returns:
        List of stem file paths, or None if demucs not available.
    """
    deps = check_audio_import_deps()
    if not deps.get('demucs'):
        print("  Warning: demucs not installed. Stem separation skipped.")
        print("  Install: pip install demucs")
        return None

    try:
        import soundfile as sf
        import torchaudio
        import numpy as np

        # Patch torchaudio.save to use soundfile (torchcodec has FFmpeg lib conflicts)
        _original_torchaudio_save = torchaudio.save
        def _patched_save(path, tensor, sample_rate, **kwargs):
            wav_data = tensor.numpy().T
            sf.write(str(path), wav_data, sample_rate, subtype='PCM_24')
        torchaudio.save = _patched_save

        from demucs.separate import main as demucs_main
        import sys

        orig_argv = sys.argv
        try:
            sys.argv = ['demucs', '--name', model, '-o', output_dir, wav_path]
            demucs_main()
        finally:
            sys.argv = orig_argv

        torchaudio.save = _original_torchaudio_save

        # Find stem files — demucs creates: output_dir/<model>/<track_name>/<stem>.wav
        stems = []
        model_dir = os.path.join(output_dir, model)
        if os.path.isdir(model_dir):
            for track_dir in sorted(os.listdir(model_dir)):
                track_path = os.path.join(model_dir, track_dir)
                if os.path.isdir(track_path):
                    for f in sorted(os.listdir(track_path)):
                        if f.endswith('.wav'):
                            stems.append(os.path.join(track_path, f))
        return stems if stems else None

    except subprocess.TimeoutExpired:
        print("  Error: demucs timed out")
        return None
    except Exception as e:
        print(f"  Error: stem separation failed: {e}")
        return None


def wav_to_midi_basic_pitch(wav_path: str, midi_path: str) -> str | None:
    """Transcribe WAV to MIDI using Basic Pitch (fallback engine)."""
    try:
        from basic_pitch.inference import predict_and_save
        output_dir = os.path.dirname(midi_path) or '.'
        # Find default ONNX model
        import basic_pitch
        _pkg = os.path.dirname(basic_pitch.__file__)
        _model_path = os.path.join(
            _pkg, 'saved_models', 'icassp_2022', 'nmp.onnx'
        )
        result = predict_and_save(
            [wav_path], output_dir,
            save_midi=True, sonify_midi=False,
            save_model_outputs=False, save_notes=False,
            model_or_model_path=_model_path,
        )
        # Basic Pitch names output as <basename>_basic_pitch.mid
        wav_base = os.path.splitext(os.path.basename(wav_path))[0]
        generated_mid = os.path.join(output_dir, f'{wav_base}_basic_pitch.mid')
        if os.path.exists(generated_mid):
            # Move to requested path
            import shutil
            shutil.move(generated_mid, midi_path)
            return midi_path
        return None
    except Exception as e:
        print(f"  Error: basic_pitch transcription failed: {e}")
        return None


def wav_to_midi_omniaudio(wav_path: str, midi_path: str) -> str | None:
    """Transcribe WAV to MIDI using OmniAudio."""
    try:
        import omniaudio
        model = omniaudio.AudioToMidi()
        midi_obj = model.predict(wav_path)
        midi_obj.save(midi_path)
        return midi_path if os.path.exists(midi_path) else None
    except Exception as e:
        print(f"  Error: omniaudio transcription failed: {e}")
        return None


def merge_midi_files(stem_midis: list[tuple[str, str]], output_path: str) -> str | None:
    """
    Merge multiple MIDI files into a single multi-track MIDI.

    Args:
        stem_midis: List of (stem_name, midi_path) tuples.
        output_path: Output merged MIDI path.

    Returns:
        Path to merged MIDI file, or None on failure.
    """
    try:
        import musicpy as mp

        merged_tracks = []
        merged_instruments = []
        merged_start_times = []

        stem_instruments = {
            'vocals': 1,
            'bass': 33,
            'drums': 1,
            'other': 1,
        }

        for stem_name, midi_path in stem_midis:
            piece = mp.read(midi_path)
            for track in piece.tracks:
                merged_tracks.append(track)
                instrument = stem_instruments.get(stem_name, 1)
                merged_instruments.append(instrument)
                merged_start_times.append(0)

        merged = mp.P(
            tracks=merged_tracks,
            instruments=merged_instruments,
            start_times=merged_start_times,
            bpm=120,
        )
        mp.write(merged, name=output_path)
        return output_path
    except Exception as e:
        print(f"  Error: MIDI merge failed: {e}")
        return None


def wav_to_midi(wav_path: str, midi_path: str, engine: str = 'omniaudio',
                postprocess: bool = True, melody_extract: bool = False) -> str | None:
    """
    Transcribe WAV to MIDI using specified engine.

    Args:
        wav_path: Input WAV file.
        midi_path: Output MIDI path.
        engine: 'omniaudio' (default) or 'basic_pitch'.
        postprocess: Whether to run post-processing on output.

    Returns:
        Path to MIDI file, or None on failure.
    """
    deps = check_audio_import_deps()

    # Try requested engine
    if engine == 'omniaudio' and deps.get('omniaudio'):
        print("  Engine: OmniAudio")
        midi_result = wav_to_midi_omniaudio(wav_path, midi_path)
    elif deps.get('basic_pitch'):
        print("  Engine: Basic Pitch (fallback)")
        midi_result = wav_to_midi_basic_pitch(wav_path, midi_path)
    else:
        print("  Warning: No transcription engine available.")
        print("  Install: pip install omniaudio basic-pitch")
        return None

    if not midi_result:
        return None

    # Post-processing
    if postprocess:
        if melody_extract and _extract_melody_pipeline is not None:
            print("  Enhanced melody extraction: detect scale, split melody, quantize...")
            try:
                import musicpy as mp
                piece = mp.read(midi_path)
                piece, info = _extract_melody_pipeline(piece, return_info=True)
                print(f"  Detected key: {info.get('key', 'unknown')}, "
                      f"BPM: {info.get('bpm', 120)}, "
                      f"Notes: {info.get('notes_after_split_melody', '?')}")
                mp.write(piece, name=midi_path)
            except Exception as e:
                print(f"  Warning: melody extraction failed, falling back to basic postprocess: {e}")
                if _postprocess_midi is not None:
                    try:
                        import musicpy as mp
                        piece = mp.read(midi_path)
                        piece = _postprocess_midi(piece)
                        mp.write(piece, name=midi_path)
                    except Exception as e2:
                        print(f"  Warning: basic postprocessing also failed: {e2}")
        elif _postprocess_midi is not None:
            print("  Post-processing: quantize, clean, normalize...")
            try:
                import musicpy as mp
                piece = mp.read(midi_path)
                piece = _postprocess_midi(piece)
                mp.write(piece, name=midi_path)
            except Exception as e:
                print(f"  Warning: post-processing failed: {e}")

    return midi_result


def separate_and_transcribe(wav_path: str, output_dir: str,
                            engine: str = 'omniaudio') -> str | None:
    """
    Full pipeline: Demucs stems → per-stem transcription → merge MIDI.

    Args:
        wav_path: Input WAV file.
        output_dir: Directory for intermediate and output files.
        engine: Transcription engine ('omniaudio' or 'basic_pitch').

    Returns:
        Path to merged MIDI file, or None on failure.
    """
    print("  Separating stems...")
    stems = separate_stems(wav_path, output_dir)

    if not stems:
        print("  Stem separation unavailable, using full audio")
        midi_path = os.path.join(output_dir, 'output.mid')
        return wav_to_midi(wav_path, midi_path, engine=engine)

    midi_files = []
    stem_names = ['vocals', 'bass', 'drums', 'other']
    for i, stem_path in enumerate(stems):
        name = stem_names[i] if i < len(stem_names) else f'stem_{i}'
        midi_path = os.path.join(output_dir, f'{name}.mid')
        print(f"  Transcribing stem: {name}")
        result = wav_to_midi(stem_path, midi_path, engine=engine)
        if result:
            midi_files.append((name, result))

    if not midi_files:
        print("  Error: no stems transcribed successfully")
        return None

    merge_path = os.path.join(output_dir, 'merged.mid')
    return merge_midi_files(midi_files, merge_path)


def import_audio(audio_path: str, midi_path: str | None = None,
                 separate: bool = True, melody_extract: bool = False) -> str | None:
    """
    Full audio import pipeline.

    Pipeline:
    1. audio → WAV
    2. (optional) Demucs stem separation
    3. Basic Pitch → MIDI

    Args:
        audio_path: Input audio file (MP3, WAV, FLAC, OGG).
        midi_path: Output MIDI path (default: same name + .mid).
        separate: Whether to run stem separation.

    Returns:
        Path to MIDI file, or None on failure.
    """
    if not os.path.exists(audio_path):
        print(f"Error: Audio file not found: {audio_path}")
        return None

    if midi_path is None:
        midi_path = os.path.splitext(audio_path)[0] + '.mid'

    tmp_dir = tempfile.mkdtemp()
    wav_path = os.path.join(tmp_dir, 'converted.wav')

    # Step 1: Convert to WAV
    print(f"  Converting {audio_path} → WAV...")
    wav_result = audio_to_wav(audio_path, wav_path)
    if not wav_result:
        _cleanup(tmp_dir)
        return None

    # Step 2: Optional stem separation
    if separate:
        print("  Separating stems...")
        stems = separate_stems(wav_path, tmp_dir)
        if stems:
            # Use vocal stem for transcription if available
            vocal = next((s for s in stems if 'vocals' in s.lower()), wav_path)
            wav_path = vocal
            print(f"  Using vocal stem for transcription")

    # Step 3: Transcribe to MIDI
    print("  Transcribing to MIDI...")
    midi_result = wav_to_midi(wav_path, midi_path, melody_extract=melody_extract)

    _cleanup(tmp_dir)

    if midi_result:
        size = os.path.getsize(midi_result)
        print(f"  MIDI: {midi_result} ({size} bytes)")
    else:
        print("  Error: MIDI transcription failed.")

    return midi_result


def _cleanup(path):
    """Remove temporary directory."""
    import shutil
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)


def _find_executable(name: str) -> str | None:
    """Find an executable in PATH."""
    for dir_path in os.environ.get('PATH', '').split(os.pathsep):
        candidate = os.path.join(dir_path, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None
