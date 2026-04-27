# MIDI Fix Judgment

You are a music transcription quality expert. Analyze the diagnostic report below and produce fix instructions.

## Context
- **Stem type**: {stem_type}
  - vocals: single-pitch monophonic melody (human voice). No overlapping notes. Typical range C3-C6 (MIDI 48-84).
  - bass: low-frequency foundation. May have sustained notes and some overlap with other instruments but itself is monophonic.
  - drums: percussion, typically MIDI channel 10. Not applicable here.
  - other: mixed accompaniment, may be polyphonic.

## Full Score
{abc_notation}

## Diagnostic Report
{diagnostic_report}
{reference_info}

## Rules (apply based on stem type)
For **vocals**:
1. No overlap — simultaneous notes must be merged into a single note (pick the dominant one)
2. Fragment chains (consecutive same-pitch) should be merged into sustained notes
3. Notes outside typical vocal range (C3=48 to C6=84) should be flagged as likely noise
4. Fragment rate > 3 events/sec for same pitch is likely a transcription artifact
5. The result must be a clean, playable single-instrument melody line

## Output Format (JSON only, no other text)
Produce a JSON object with:
```json
{{
  "summary": "brief assessment of the issues",
  "fixes": [
    {{
      "type": "merge_overlap" | "merge_fragments" | "remove_out_of_range" | "normalize_velocity" | "estimate_bpm",
      "description": "what to do",
      "params": {{ ... specific parameters ... }},
      "priority": "high" | "medium" | "low"
    }}
  ],
  "estimated_clean_note_count": <number>
}}
```
