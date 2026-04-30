# Tools Codemap

**Last Updated:** 2026-04-30

## Tool Categories

```
tools/
├── analysis/          — Musical analysis (read-only)
│   ├── analyze_harmony.py
│   ├── extract_melody.py
│   └── voice_detection.py
├── harmony/           — Harmony generation (writes)
│   └── generate_accompaniment.py
├── arrangement/       — Style-specific arrangement (writes)
│   ├── arrange_piano.py
│   ├── arrange_strings.py
│   ├── arrange_winds.py
│   └── transposition.py
├── expression/        — Performance expression (writes)
│   ├── add_pedal.py
│   ├── adjust_velocity.py
│   └── timing_variation.py
├── validation/        — Quality checks (read-only)
│   ├── range_check.py
│   └── theory_check.py
└── transcription_to_piano/  — Audio transcription helpers
    └── __init__.py
```

## Analysis Tools (Read-Only)

### AnalyzeHarmonyTool

| Attribute | Value |
|-----------|-------|
| Name | `analyze_harmony` |
| Location | `tools/analysis/analyze_harmony.py` |
| Purpose | Detect chord progression from piece |
| Key Fix | `_get_start_times` now uses musicpy interval gaps for cumulative timing |

**Interface:**
```python
run(piece, granularity="measure") -> list[{measure, chord, root, quality}]
```

**Design:**
- Groups notes by time window across ALL tracks
- Uses `mp.alg.detect_chord_by_root()` for structured detection
- Falls back to `mp.alg.detect()` with regex cleanup for `sort as [...]` and `omit X` noise
- Computes start times from musicpy `interval` attribute (cumulative gaps, not raw values)

### ExtractMelodyTool

| Attribute | Value |
|-----------|-------|
| Name | `extract_melody` |
| Location | `tools/analysis/extract_melody.py` |
| Purpose | Extract melody from piece using musicpy built-ins |

**Interface:**
```python
run(piece, method="split_melody") -> dict
```

### VoiceDetectionTool

| Attribute | Value |
|-----------|-------|
| Name | `voice_detection` |
| Location | `tools/analysis/voice_detection.py` |
| Purpose | Identify voice roles in multi-track piece |

**Interface:**
```python
run(piece) -> dict  # {melody, harmony, bass, counter_melody}
```

## Harmony Tools (Write)

### GenerateAccompanimentTool

| Attribute | Value |
|-----------|-------|
| Name | `generate_accompaniment` |
| Location | `tools/harmony/generate_accompaniment.py` |
| Purpose | Generate piano accompaniment from chord progression |

**Interface:**
```python
run(harmony, style="classical", pattern="broken_chord",
    voicing="closed", density="medium", total_measures=None)
    -> mp.chord
```

**Key Fixes:**
- `_chord_str_to_notes()` always parses root+quality manually (avoids `mp.chord('C11')` octave misinterpretation)
- `_broken_chord()` produces 8 notes per measure (Alberti bass: root-top-mid-top pattern, 4 beats x 2 eighth-notes)
- Regex cleanup for `sort as [...]` and `omit X` noise in chord names
- `_parse_quality()` handles extended chords (7, 9, 11, 13) with major/minor variants

**Patterns:**
- `broken_chord` — Alberti bass style, 8 eighth-notes per bar
- `arpeggio` — Sweeping arpeggios, configurable density (sparse/medium/dense)
- `block_chord` — Block chords with octave bass

## Arrangement Tools (Write)

### ArrangePianoTool

| Attribute | Value |
|-----------|-------|
| Location | `tools/arrangement/arrange_piano.py` |
| Purpose | Piano arrangement in classical/romantic/pop styles |

### ArrangeStringsTool

| Attribute | Value |
|-----------|-------|
| Location | `tools/arrangement/arrange_strings.py` |
| Purpose | String ensemble arrangement |

### ArrangeWindsTool

| Attribute | Value |
|-----------|-------|
| Location | `tools/arrangement/arrange_winds.py` |
| Purpose | Wind ensemble arrangement |

### TranspositionTool

| Attribute | Value |
|-----------|-------|
| Location | `tools/arrangement/transposition.py` |
| Purpose | Transpose piece to different key |

## Expression Tools (Write)

### AddPedalTool

| Attribute | Value |
|-----------|-------|
| Location | `tools/expression/add_pedal.py` |
| Purpose | Add sustain pedal markings |

### AdjustVelocityTool

| Attribute | Value |
|-----------|-------|
| Location | `tools/expression/adjust_velocity.py` |
| Purpose | Adjust note velocities for dynamics |

### TimingVariationTool

| Attribute | Value |
|-----------|-------|
| Location | `tools/expression/timing_variation.py` |
| Purpose | Micro-timing variations for humanization |

## Validation Tools (Read-Only)

### RangeCheckTool

| Attribute | Value |
|-----------|-------|
| Location | `tools/validation/range_check.py` |
| Purpose | Verify notes are within instrument range |

**Interface:**
```python
run(piece, instrument="piano") -> {passed: bool, issues: list[str]}
```

### TheoryCheckTool

| Attribute | Value |
|-----------|-------|
| Location | `tools/validation/theory_check.py` |
| Purpose | Music theory validation (parallel fifths, etc.) |

## Tool Registry

| File | Purpose |
|------|---------|
| `agent/tool_registry.py` | Global tool registration, piece context management |
| `agent/prompt_templates.py` | LLM prompt templates for tools |

**Context management:**
```python
set_piece_context(piece)  # Store piece for tool access
get_piece_context()       # Retrieve current piece
```

## Related Areas

- [pipeline.md](./pipeline.md) — How tools are invoked in the role pipeline
- [io.md](./io.md) — Input/output utilities used by tools
