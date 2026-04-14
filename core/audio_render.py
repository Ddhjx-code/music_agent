"""
Audio rendering module.

Renders MIDI files to WAV or MP3 using fluidsynth + optional ffmpeg.
"""

import os
import shutil
import subprocess
import tempfile
import wave


# Default SoundFont search paths
SOUNDFONT_CANDIDATES = [
    # Homebrew fluid-synth default
    '/opt/homebrew/Cellar/fluid-synth/2.5.3/share/fluid-synth/sf2/VintageDreamsWaves-v2.sf2',
    '/opt/homebrew/share/fluid-synth/sf2/VintageDreamsWaves-v2.sf2',
    # System locations
    '/usr/share/sounds/sf2/FluidR3_GM.sf2',
    '/usr/share/sounds/sf2/TimGM6mb.sf2',
    # Project-local
    'assets/FluidR3_GM.sf2',
]


def discover_soundfont(paths: list[str] | None = None) -> str | None:
    """Find an available SoundFont file."""
    candidates = paths or SOUNDFONT_CANDIDATES
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def apply_audio_postfx(input_wav: str, output_wav: str,
                       reverb: bool = False,
                       compression: bool = False,
                       normalize: bool = True,
                       target_db: str = '-1.0') -> str | None:
    """
    Apply post-processing effects to rendered audio.

    Uses ffmpeg audio filters:
    - reverb: Add echo/reverb effect
    - compression: Light dynamic range compression
    - normalize: Peak normalize to target dB

    Args:
        input_wav: Input WAV file path.
        output_wav: Output WAV file path.
        reverb: Apply reverb effect.
        compression: Apply compression.
        normalize: Apply peak normalization.
        target_db: Target peak level in dB (default: -1.0).

    Returns:
        Path to processed WAV file, or None on failure.
    """
    if not (reverb or compression or normalize):
        shutil.copy2(input_wav, output_wav)
        return output_wav

    filters = []
    if reverb:
        filters.append('aecho=0.8:0.88:60:0.4')
    if compression:
        filters.append('acompressor=threshold=0.089:ratio=9:attack=200:release=1000')
    if normalize:
        filters.append(f'loudnorm=I={target_db}')

    filter_str = ','.join(filters)

    try:
        result = subprocess.run(
            ['ffmpeg', '-y', '-i', input_wav, '-af', filter_str, output_wav],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0 or not os.path.exists(output_wav):
            print(f"  Error: post-FX failed: {result.stderr[:200]}")
            return None
        return output_wav
    except FileNotFoundError:
        print("  Error: ffmpeg not found for post-processing")
        return None
    except subprocess.TimeoutExpired:
        print("  Error: post-FX timed out")
        return None


def render_wav(midi_path: str, wav_path: str, sf2_path: str,
               options: dict | None = None) -> str | None:
    """
    Render MIDI to WAV using fluidsynth.

    Args:
        midi_path: Path to input MIDI file.
        wav_path: Path to output WAV file.
        sf2_path: Path to SoundFont file.
        options: Optional dict with keys:
            - reverb: float (0-1), reverb level
            - chorus: float (0-1), chorus level
            - postfx: dict, pass to apply_audio_postfx

    Returns:
        Path to WAV file on success, None on failure.
    """
    options = options or {}
    raw_path = wav_path.rsplit('.', 1)[0] + '.raw'

    cmd = ['fluidsynth', '-ni']
    if options.get('reverb'):
        cmd.extend(['-r', str(options['reverb'])])
    if options.get('chorus'):
        cmd.extend(['-c', str(options['chorus'])])
    cmd.extend(['-F', raw_path, sf2_path, midi_path])

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120
        )
        if not os.path.exists(raw_path):
            print(f"  Error: fluidsynth failed: {result.stderr[:200]}")
            return None

        with open(raw_path, 'rb') as fin, wave.open(wav_path, 'wb') as wav_out:
            wav_out.setnchannels(2)
            wav_out.setsampwidth(2)
            wav_out.setframerate(44100)
            wav_out.writeframes(fin.read())

        os.remove(raw_path)

        # Apply post-FX if requested
        postfx = options.get('postfx')
        if postfx:
            postfx_path = wav_path.rsplit('.', 1)[0] + '_postfx.wav'
            postfx_result = apply_audio_postfx(wav_path, postfx_path, **postfx)
            if postfx_result:
                shutil.move(postfx_path, wav_path)

        return wav_path
    except FileNotFoundError:
        print("  Error: fluidsynth not found. Install with: brew install fluidsynth")
        return None
    except subprocess.TimeoutExpired:
        print("  Error: fluidsynth timed out")
        return None


def render_timidity(midi_path: str, wav_path: str,
                    reverb: bool = True,
                    chorus: bool = True,
                    options: dict | None = None) -> str | None:
    """
    Render MIDI to WAV using Timidity++.

    Args:
        midi_path: Path to input MIDI file.
        wav_path: Path to output WAV file.
        reverb: Enable reverb effect.
        chorus: Enable chorus effect.
        options: Additional Timidity options dict.

    Returns:
        Path to WAV file on success, None on failure.
    """
    cmd = ['timidity', midi_path, '-Ow', '-o', wav_path]

    if reverb:
        cmd.append('-Or')
    if chorus:
        cmd.append('-Oc')

    if options:
        for key, value in options.items():
            cmd.append(f'{key}{value}')

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120
        )
        if not os.path.exists(wav_path):
            print(f"  Error: timidity failed: {result.stderr[:200]}")
            return None
        return wav_path
    except FileNotFoundError:
        print("  Error: timidity not found. Install with: brew install timidity")
        return None
    except subprocess.TimeoutExpired:
        print("  Error: timidity timed out")
        return None


def render_mp3(midi_path: str, mp3_path: str, sf2_path: str) -> str | None:
    """
    Render MIDI to MP3 via WAV intermediate.

    Args:
        midi_path: Path to input MIDI file.
        mp3_path: Path to output MP3 file.
        sf2_path: Path to SoundFont file.

    Returns:
        Path to MP3 file on success, None on failure.
    """
    # Step 1: Render to WAV
    wav_path = mp3_path.rsplit('.', 1)[0] + '.wav'
    wav_result = render_wav(midi_path, wav_path, sf2_path)
    if not wav_result:
        return None

    # Step 2: Convert WAV to MP3 via ffmpeg
    try:
        result = subprocess.run(
            ['ffmpeg', '-y', '-i', wav_path, '-codec:a', 'libmp3lame',
             '-qscale:a', '2', mp3_path],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            print(f"  Error: ffmpeg failed: {result.stderr[:200]}")
            return None
    except FileNotFoundError:
        print("  Error: ffmpeg not found. Install with: brew install ffmpeg")
        return None
    except subprocess.TimeoutExpired:
        print("  Error: ffmpeg timed out")
        return None
    finally:
        # Clean up WAV intermediate
        if os.path.exists(wav_path):
            os.remove(wav_path)

    return mp3_path


def render_audio(midi_path: str, output_path: str,
                 sf2_path: str | None = None,
                 format: str | None = None,
                 engine: str = 'fluidsynth',
                 expression: bool = False,
                 options: dict | None = None) -> str | None:
    """
    Unified entry point for audio rendering.

    Args:
        midi_path: Path to input MIDI file.
        output_path: Desired output path.
        sf2_path: Optional SoundFont path.
        format: Optional format override ('wav' or 'mp3').
        engine: 'fluidsynth' (default) or 'timidity'.
        expression: Whether to apply expression pre-processing.
        options: Additional render options.

    Returns:
        Path to rendered audio file, or None on failure.
    """
    options = options or {}

    if format is None:
        ext = os.path.splitext(output_path)[1].lower()
        format = 'mp3' if ext == '.mp3' else 'wav'

    # Apply expression pre-processing if requested
    if expression:
        try:
            import musicpy as mp
            from core.audio_render_expression import apply_full_expression
            piece = mp.read(midi_path)
            piece = apply_full_expression(piece)
            expr_midi_path = midi_path.rsplit('.', 1)[0] + '_expr.mid'
            mp.write(piece, name=expr_midi_path)
            midi_path = expr_midi_path
        except Exception as e:
            print(f"  Warning: expression pre-processing failed: {e}")

    sf2 = sf2_path or discover_soundfont()

    if format == 'mp3':
        wav_path = output_path.rsplit('.', 1)[0] + '.wav'
        if engine == 'timidity':
            wav_result = render_timidity(midi_path, wav_path, **options)
        else:
            if sf2 is None:
                print("  Warning: No SoundFont found.")
                return None
            wav_result = render_wav(midi_path, wav_path, sf2, options=options)

        if not wav_result:
            return None

        try:
            result = subprocess.run(
                ['ffmpeg', '-y', '-i', wav_path, '-codec:a', 'libmp3lame',
                 '-qscale:a', '2', output_path],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode != 0:
                print(f"  Error: ffmpeg failed: {result.stderr[:200]}")
                return None
        except FileNotFoundError:
            print("  Error: ffmpeg not found.")
            return None
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)

        return output_path

    else:  # wav
        if engine == 'timidity':
            return render_timidity(midi_path, output_path, **options)
        else:
            if sf2 is None:
                print("  Warning: No SoundFont found.")
                return None
            return render_wav(midi_path, output_path, sf2, options=options)
