# Pipeline Codemap

**Last Updated:** 2026-04-30

## Entry Points

- `main.py` — CLI entry point
- `core/orchestrator.py` — RoleOrchestrator class
- `core/audio_import.py` — Audio-to-MIDI pipeline

## Architecture

```
                         main.py
                           |
            +--------------+---------------+
            |                              |
       is_audio_input?                  MIDI input
            |                              |
   import_audio_to_midi()            load_midi()
            |                              |
   [audio_import pipeline]          generate_summary()
            |                              |
            v                              v
        imported.mid +---------------+ piece
                            |
                +-----------+-----------+
                |                       |
            --algo mode             LLM mode
                |                       |
        ArrangePianoTool      RoleOrchestrator.run()
                                      |
                  +-------------------+-------------------+
                  |                   |                   |
            Phase 0-4 pipeline   Critic bounce-back   save + render
```

## Audio Import Pipeline

```
Audio file (wav/mp3/flac/ogg)
    |
    v
1. audio_to_wav()           — Convert to WAV if needed
    |
    v
2. separate_stems()         — Demucs: vocals, bass, drums, other
    |
    v
3. wav_to_midi_basic_pitch() — Per-stem transcription to MIDI
    |
    v
4. fix_midi()               — Per-stem MIDI cleanup (overlaps, fragments, range)
    |
    v
5. merge_midi_files()       — Merge all stems into single MIDI
```

## Orchestrator Pipeline (RoleOrchestrator)

```
Phase 0: MIDI Fix
    — Clean fragmentation, overlaps, out-of-range notes
    — Uses midi_fixer.fix_midi() with rule-based + LLM judgment

Phase 1: Pre-Analysis (tools only)
    — AnalystRole runs analysis tools without LLM
    — Voice detection, harmony analysis

Phase 2: Planning
    — PlannerRole uses LLM to determine execution plan
    — Output: {"phases": [...], "params": {...}}

Phase 3: Execute Planned Phases
    — analysis    → AnalystRole (full with LLM)
    — arrangement → ArrangerRole (with bounce-back)
    — harmonist   → HarmonistRole
    — expression  → ExpressionRole (with bounce-back)

Phase 4: Critic Review
    — CriticRole validates output
    — Bounce-back loop: up to MAX_BOUNCES (2) retries per role
    — Only triggers on high-severity issues
```

## Role Architecture

| Role | Purpose | Key Methods | Dependencies |
|------|---------|-------------|--------------|
| AnalystRole | Pre-analysis of piece | `run_tools_only()`, `run()` | Voice detection, harmony analysis tools |
| PlannerRole | Create execution plan | `run()` | LLM, prompt templates |
| ArrangerRole | Musical arrangement | `run()` | LLM, arrangement tools |
| HarmonistRole | Harmony generation | `run()` | LLM, accompaniment tools |
| ExpressionRole | Add expression/dynamics | `run()` | LLM, expression tools |
| CriticRole | Validate output quality | `run()` | LLM, validation tools |

## RoleContext

Shared context between roles:
- `instruction` — User's natural language request
- `plan` — Execution plan from PlannerRole
- `analyst_report` — Analysis results
- `arrangement_report` — Arrangement results
- `harmony_report` — Harmony results
- `expression_report` — Expression results
- `critic_issues` — Issues flagged by Critic for bounce-back

## Data Flow

```
User instruction + MIDI piece
    |
    v
RoleContext created
    |
    v
Phase 0: MIDI Fix → cleaned piece
    |
    v
Phase 1: Pre-analysis → analyst_report
    |
    v
Phase 2: Planning → plan (phases + params)
    |
    v
Phase 3: Execute phases → updated piece after each
    |
    v
Phase 4: Critic → if issues, bounce back to specific roles
    |              re-run critic until passed or max bounces
    v
Final arranged piece → save_midi() → optionally render_audio()
```

## Key Files

| File | Purpose |
|------|---------|
| `core/orchestrator.py` | RoleOrchestrator class, Phase 0-4 pipeline, bounce-back logic |
| `core/roles/base.py` | Role abstract class, RoleContext |
| `core/roles/analyst_role.py` | Pre-analysis and full analysis |
| `core/roles/planner_role.py` | LLM-driven planning |
| `core/roles/arranger_role.py` | Musical arrangement |
| `core/roles/harmonist_role.py` | Harmony generation |
| `core/roles/expression_role.py` | Expression and dynamics |
| `core/roles/critic_role.py` | Quality validation |
| `core/midi_fixer.py` | MIDI cleanup pipeline (analysis → LLM → apply fixes) |
| `core/audio_import.py` | Audio-to-MIDI import pipeline |
| `core/audio_render.py` | MIDI-to-audio rendering with post-processing |
| `core/audio_postprocess.py` | Audio post-processing (reverb, compression, normalization) |

## Related Areas

- [tools.md](./tools.md) — Tool implementations used by roles
- [io.md](./io.md) — MIDI/ABC conversion, audio rendering
- [test-fixtures.md](./test-fixtures.md) — Test coverage
