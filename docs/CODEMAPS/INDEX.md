# Music Agent Codemaps Index

**Last Updated:** 2026-04-30

## Architecture Overview

```
Audio/MIDI Input
    |
    v
+-------------------+
|    main.py (CLI)  |  -- Entry point, format detection, mode selection
+-------------------+
    |
    +-- MIDI input -----> core/music_io.py (load)
    |
    +-- Audio input ----> core/audio_import.py (Demucs -> Basic Pitch -> merge)
    |                          |
    |                          v
    |                     core/midi_fixer.py (per-stem cleanup)
    |
    v
+-------------------+
|  core/json_schema |  -- Structured JSON summary of piece
+-------------------+
    |
    +-- --algo mode ---> tools/arrangement/arrange_piano.py
    |
    +-- LLM mode -----> core/orchestrator.py (RoleOrchestrator)
                              |
                              v
                    Multi-role pipeline (Phases 0-4)
```

## Codemap Documents

| Document | Scope |
|----------|-------|
| [pipeline.md](./pipeline.md) | Full pipeline: CLI, audio import, orchestrator, roles |
| [tools.md](./tools.md) | Analysis, harmony, arrangement, expression, validation tools |
| [io.md](./io.md) | MIDI/ABC conversion, audio rendering, JSON schema |
| [test-fixtures.md](./test-fixtures.md) | Test fixtures and test modules |

## Key Design Principles

- **musicpy-first**: All music processing uses musicpy built-in functions, not custom algorithms
- **LLM loop**: LLM participates in a decision loop with JSON feedback between steps
- **Multi-role orchestration**: Six specialized roles (Planner, Analyst, Arranger, Harmonist, Expression, Critic)
- **Critic bounce-back**: Up to 2 retries per role when Critic identifies high-severity issues

## External Dependencies

| Package | Purpose |
|---------|---------|
| musicpy >= 0.6.0 | Core music representation and algorithms |
| langchain / langchain-openai | LLM integration |
| mido | MIDI file I/O |
| pretty_midi | MIDI analysis and manipulation |
| basic-pitch | Audio-to-MIDI transcription |
| demucs | Stem separation |
| pytest / pytest-cov | Testing |
