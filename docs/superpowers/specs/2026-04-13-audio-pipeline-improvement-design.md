# Audio Pipeline Improvement Design

Date: 2026-04-13

## Problem Statement

Current WAV→MIDI transcription and MIDI→WAV rendering both produce poor quality results:

**WAV→MIDI issues:**
- Basic Pitch struggles with multi-voice (melody + accompaniment mixed)
- Rhythm and note duration inaccurate
- Note recognition imprecise

**MIDI→WAV issues:**
- SoundFont quality poor or missing
- No expression processing (uniform velocity)
- Incorrect instrument mapping
- No reverb/chorus effects

## Architecture

```
WAV → MIDI (Audio Import)
┌─────────────┐
│  WAV input   │
└──────┬──────┘
       │
  ┌────▼────────────┐
  │ Demucs stems    │  vocals/drums/bass/other
  └────┬────────────┘
       │
  ┌────▼────────────┐     ┌──────────────────┐
  │ Per-stem trans. │──→  │ Merge MIDI        │
  │ OmniAudio       │     │ - multi-track     │
  │ + basic_pitch   │     │ - instrument sep. │
  └────┬────────────┘     └────────┬─────────┘
       │                           │
  ┌────▼────────────┐     ┌────────▼─────────┐
  │ Post-processing │     │ Expression tags  │
  │ - quantize      │     │ - velocity map   │
  │ - clean notes   │     │ - pedal events   │
  └─────────────────┘     └──────────────────┘

MIDI → WAV (Audio Render)
┌─────────────┐
│  MIDI input  │
└──────┬──────┘
       │
  ┌────▼────────────┐
  │ Expression prep │
  │ - velocity adj. │
  │ - pedal add     │
  │ - rubato        │
  └────┬────────────┘
       │
  ┌────▼────────────┐     ┌──────────────────┐
  │ FluidSynth/Tim. │──→  │ Post-FX           │
  │ - quality SF2   │     │ - reverb          │
  │ - chorus/reverb │     │ - compression     │
  └─────────────────┘     └──────────────────┘
```

## Part A: Improved WAV→MIDI Transcription

### A1. OmniAudio Integration

- Add `omniaudio` as optional dependency alongside `basic_pitch`
- OmniAudio handles monophonic and polyphonic transcription
- Falls back to basic_pitch if omniaudio unavailable

### A2. Per-Stem Transcription Pipeline

- After Demucs separates stems (vocals, drums, bass, other)
- Each stem is transcribed independently via OmniAudio
- Results merged into separate MIDI tracks per instrument group

### A3. Post-Processing Module

New module `core/audio_postprocess.py`:
- **Rhythm quantization**: Snap note start times to nearest beat subdivision (1/4, 1/8, 1/16)
- **Note duration cleanup**: Normalize durations to musical values
- **Duplicate removal**: Remove overlapping notes on same pitch/channel
- **Velocity normalization**: Scale velocities to reasonable range (40-110)
- **Tempo estimation**: Estimate BPM from note onsets for better quantization reference

## Part B: Improved MIDI→WAV Rendering

### B1. Expression Pre-Processing

Extend existing expression tools:

- **Velocity mapping**: Analyze melody/accompaniment roles, apply dynamic velocity ranges
  - Melody: 70-110 (expressive, varies by phrase)
  - Accompaniment: 40-70 (subtle background)
  - Bass: 60-90 (solid foundation)
- **Phrase-based expression**: Detect phrase boundaries, add crescendo/decrescendo
- **Rubato**: Add slight timing variations for human feel (±10ms, configurable)

### B2. Quality SoundFont Support

- Bundle a high-quality free SoundFont (e.g., Salamander Piano SF2)
- Expand `discover_soundfont()` to search more locations
- Support multiple SoundFonts per instrument group

### B3. Timidity++ Integration

Add `render_timidity()` function:
- Use Timidity++ as alternative renderer to FluidSynth
- Supports `-Or` (reverb), `-Oc` (chorus) flags
- Configurable via render options dict

### B4. Post-Processing Effects

After raw rendering:
- **Reverb**: Apply convolution reverb via sox or ffmpeg filter
- **Compression**: Light compression for better dynamic range
- **Normalization**: Peak normalize to -1dB

## Part C: Interface Changes

### audio_import.py

```python
def wav_to_midi(wav_path, midi_path, engine='omniaudio', postprocess=True):
    """Transcribe WAV to MIDI with configurable engine and post-processing."""

def separate_and_transcribe(wav_path, output_dir, engine='omniaudio'):
    """Full pipeline: Demucs stems → per-stem transcription → merge."""
```

### audio_render.py

```python
def render_wav(midi_path, wav_path, sf2_path, options=None):
    """Render with expression options: reverb, chorus, expression."""

def render_timidity(midi_path, wav_path, options=None):
    """Alternative rendering via Timidity++."""

def apply_expression(piece, profile='piano'):
    """Pre-process MIDI with expression: velocity, timing, pedals."""
```

## Dependencies

New optional dependencies:
- `omniaudio` - polyphonic transcription engine
- `timidity` or `timidity++` - software MIDI synthesizer
- `sox` (optional) - post-processing effects
- Higher-quality SoundFont files (bundled or auto-downloaded)

Existing dependencies unchanged:
- `demucs` - stem separation
- `basic_pitch` - fallback transcription
- `fluidsynth` - primary renderer
- `ffmpeg` - format conversion

## Testing Strategy

- Unit tests for postprocessing functions (quantize, clean, normalize)
- Integration tests for full wav→mid→wav round-trip
- Mock OmniAudio and Timidity subprocesses
- Test with and without each optional dependency

## Risks

- OmniAudio may have different output format than basic_pitch — need adapter
- SoundFont bundling increases repo size — may prefer auto-download
- Timidity++ quality varies by platform — need good defaults
- Per-stem transcription multiplies processing time — add progress feedback
