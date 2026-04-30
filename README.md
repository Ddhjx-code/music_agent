# Music Agent

AI-driven music arrangement pipeline that converts audio/MIDI input into arranged piano scores with ABC notation and audio rendering.

## Quick Start

```bash
# Prerequisites
pip install -r requirements.txt
brew install abcmidi abc2ps fluid-synth  # for ABC output and audio rendering

# Arrange a MIDI file to classical piano
python main.py input.mid "改成古典钢琴"

# Audio input (wav/mp3/flac/ogg)
python main.py input.wav "改成钢琴演奏" --format wav

# Output MIDI only
python main.py input.mid "改成流行钢琴"

# Output WAV with custom SoundFont
python main.py input.mid "改成浪漫钢琴" --format wav --sf2 /path/to/sf2
```

## Architecture

```
Input (MIDI / WAV / MP3 / FLAC)
    |
    +-- MIDI input ──────> load_midi()
    |
    +-- Audio input ────> Demucs stem separation → Basic Pitch transcription → fix_midi() → merge
    |
    v
+-------------------+
|  Algorithm mode   |  ArrangePianoTool (no LLM, --algo flag)
|  LLM mode         |  RoleOrchestrator (6-role pipeline)
+-------------------+
    |
    v
Output (.mid / .abc / .wav)
```

### Pipeline Phases (LLM Mode)

```
Phase 0: MIDI Fix          — Clean overlaps, fragments, out-of-range notes
Phase 1: Pre-Analysis      — Voice detection + harmony analysis (tools only)
Phase 2: Planning          — LLM creates execution plan
Phase 3: Execute           — arrangement → harmonist → expression
Phase 4: Critic Review     — Validate output, bounce-back on high-severity issues (max 2 retries)
```

### Roles

| Role | Purpose | Phase |
|------|---------|-------|
| AnalystRole | Analyze melody, harmony, voices | Phase 1 |
| PlannerRole | Create execution plan from user instruction | Phase 2 |
| ArrangerRole | Musical arrangement decisions | Phase 3 |
| HarmonistRole | Generate accompaniment | Phase 3 |
| ExpressionRole | Add dynamics, pedal, timing | Phase 3 |
| CriticRole | Validate output quality | Phase 4 |

### Tools

| Category | Tool | Purpose |
|----------|------|---------|
| Analysis | `ExtractMelodyTool` | Extract melody using musicpy split_melody |
| Analysis | `AnalyzeHarmonyTool` | Detect chord progression per measure |
| Analysis | `VoiceDetectionTool` | Identify voice roles in multi-track piece |
| Harmony | `GenerateAccompanimentTool` | Generate accompaniment (broken chord / arpeggio / block chord) |
| Arrangement | `ArrangePianoTool` | Piano arrangement (classical / romantic / pop) |
| Arrangement | `ArrangeStringsTool` | String ensemble arrangement |
| Arrangement | `ArrangeWindsTool` | Wind ensemble arrangement |
| Arrangement | `TranspositionTool` | Transpose to different key |
| Expression | `AddPedalTool` | Sustain pedal markings |
| Expression | `AdjustVelocityTool` | Velocity dynamics |
| Expression | `TimingVariationTool` | Micro-timing humanization |
| Validation | `RangeCheckTool` | Verify instrument range |
| Validation | `TheoryCheckTool` | Music theory validation |

### Output Formats

| Format | Tool | Description |
|--------|------|-------------|
| `.mid` | musicpy | Arranged MIDI file |
| `.abc` | core/midi_to_abc.py | ABC notation (K:C, L:1/8, multi-voice) |
| `.png` | abc2ps | Sheet music from ABC |
| `.wav` | fluidsynth / timidity | Audio rendering with SoundFont |
| `.mp3` | ffmpeg + fluidsynth | MP3 audio |

## Test Results

240 tests passing. 7 pre-existing failures in audio import pipeline (unrelated `separate_stems` API issue).

```bash
python -m pytest tests/ -v
```

## Key Design Decisions

- **musicpy-first**: All music processing uses musicpy built-in functions
- **LLM loop**: LLM participates in a decision loop with JSON feedback between steps
- **Decoupled tools**: Each tool has a single responsibility, orchestrated by roles
- **ABC K:C always**: No key signature auto-detection — every pitch has explicit accidental
- **Piano range safe**: All notes validated within A0-C8 (MIDI 21-108)

## Dependencies

| Package | Purpose |
|---------|---------|
| musicpy >= 0.6.0 | Core music representation |
| langchain / langchain-openai | LLM integration |
| mido | MIDI file I/O |
| pretty_midi | MIDI analysis |
| basic-pitch | Audio-to-MIDI transcription |
| demucs | Stem separation |
| fluidsynth / abcmidi | Audio rendering and ABC conversion |

## Environment

Requires `OPENAI_API_KEY` for LLM mode. Use `--algo` flag to skip LLM entirely.
