# Test Fixtures Codemap

**Last Updated:** 2026-04-30

## Fixture Definitions

### `tests/conftest.py`

All test MIDI files generated programmatically using musicpy — no external dependencies.

| Fixture | Description |
|---------|-------------|
| `simple_melody_piece` | 2-track: melody (RH) + chords (LH). C major, 4/4, 120 BPM, 4 measures. Melody: C-D-E-F-G-F-E-D-C-E-G-C6-G-F-E-D. Chords: C-G-Am-F |
| `pop_song_piece` | 3-track: vocal + guitar + bass. G major, 4/4, 100 BPM. Vocal melody, strummed guitar chords, quarter-note bass line |
| `single_track_piece` | Monophonic C major scale, 8 quarter notes, 120 BPM |
| `multi_track_piece` | 3-track: harmony (block chords) + bass (half notes) + effect (short notes, excluded by duration filter). 8 measures, C major, 120 BPM |
| `four_voice_piece` | SATB voicing in C major, 4/4, 120 BPM, 4 measures. Soprano/Alto/Tenor/Bass tracks |
| `full_harmony_piece` | 5-track: melody + harmony + counter-melody + bass + sparse effect. C major, 4/4, 120 BPM, 4 measures |
| `midi_dir` | Creates temp directory with fixture MIDI files via `mp.write()` |

## Key Interval Semantics

musicpy `interval` field represents **gaps between consecutive notes**, not absolute positions:
- `interval[0]` = time offset to first note from zero
- `interval[i]` = gap from note[i-1] end to note[i] start

**Example** (harmony track with chords at each measure):
```python
harmony_notes.append(mp.note('C', 3, duration=1.0))
harmony_intervals.append(chord_start - cum)  # Gap to first note of new chord
harmony_notes.append(mp.note('E', 3, duration=1.0))
harmony_intervals.append(0.0)  # Simultaneous notes have 0 gap
```

## Test Modules

| File | Scope |
|------|-------|
| `tests/test_arrange_piano.py` | Piano arrangement (classical/romantic/pop styles, range validation) |
| `tests/test_melody_extraction_pipeline.py` | Melody extraction + tempo estimation |
| `tests/test_audio_postprocess.py` | Velocity normalization, sustained note merge, key detection |
| `tests/test_audio_import.py` | Audio-to-MIDI import pipeline |
| `tests/test_audio_pipeline_integration.py` | Full audio round-trip tests |

## Related Areas

- [pipeline.md](./pipeline.md) — How fixtures are used in pipeline tests
- [tools.md](./tools.md) — Tools being tested
