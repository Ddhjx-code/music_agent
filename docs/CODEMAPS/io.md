# I/O Codemap

**Last Updated:** 2026-04-30

## MIDI/ABC Conversion

### `core/midi_to_abc.py`

Complete rewrite — uses L:1/8 (not L:1/16) to avoid abc2midi ambiguity between duration suffixes and pitch octaves.

| Function | Purpose |
|----------|---------|
| `midi_to_abc(midi_path, abc_path)` | Convert MIDI → ABC with K:C, multi-voice |
| `abc_to_midi(abc_path, midi_path)` | Convert ABC → MIDI via abc2midi CLI |
| `abc_to_png(abc_path, png_path)` | Convert ABC → sheet music PNG via abcm2ps |
| `read_abc(path)` | Read ABC file contents |
| `write_abc(text, path)` | Write ABC text to file |

**Key design decisions:**
- L:1/8 with UNIT_PER_BEAT=2, BAR_LEN=8 for 4/4 time
- Bar-by-bar processing with occupancy grid — no cross-bar ties
- Voice-grouped output format (all bars per voice together)
- Duration decomposition into standard values [8,6,4,3,2,1] joined by ties

## Audio Rendering

### `core/audio_render.py`

| Function | Purpose |
|----------|---------|
| `render_audio(midi_path, output_path, ...)` | Unified entry — renders MIDI → WAV/MP3 |
| `render_wav(midi_path, wav_path, sf2_path)` | Render via fluidsynth + SoundFont |
| `render_timidity(midi_path, wav_path)` | Render via Timidity++ |
| `render_mp3(midi_path, mp3_path, sf2_path)` | Render via WAV + ffmpeg libmp3lame |
| `apply_audio_postfx(input_wav, output_wav, ...)` | Post-processing: reverb, compression, loudnorm |
| `discover_soundfont(paths)` | Find available SoundFont file |

**Engine options:** fluidsynth (default), timidity
**Post-processing:** EBU R128 loudness normalization, reverb, compression

## Audio Post-Processing

### `core/audio_postprocess.py`

| Function | Purpose |
|----------|---------|
| `estimate_tempo(piece)` | BPM estimation from note timing |
| `normalize_velocities(piece)` | Scale velocities to target range |
| `merge_sustained_notes(piece)` | Merge same-pitch notes played close together |
| `postprocess_midi(piece)` | Runs all steps: tempo, velocity, merge |
| `extract_melody_pipeline(piece)` | Key detection + single-track melody extraction |

## JSON Schema

### `core/json_schema.py`

Structured JSON summary of MIDI piece for LLM context.

## Related Areas

- [pipeline.md](./pipeline.md) — How I/O fits into the pipeline
- [tools.md](./tools.md) — Tools that consume I/O outputs
