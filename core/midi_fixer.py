"""
MIDI fix pipeline: analysis → LLM judgment → tool execution.

Link: MIDI → analysis → LLM judgment → fix instructions → tool execution → fixed MIDI
"""

import json
import os

import pretty_midi
from dotenv import load_dotenv

load_dotenv()

from core.midi_analysis import MidiDiagnostic


def build_diagnostic_context(diagnostic: MidiDiagnostic) -> str:
    """Convert diagnostic into LLM-readable context."""
    return diagnostic.to_report()


def build_fix_prompt(diagnostic_context: str, stem_type: str, reference_info: str = "") -> str:
    """Build the LLM prompt for MIDI fix judgment."""
    prompt = f"""You are a music transcription quality expert. Analyze the diagnostic report below and produce fix instructions.

## Context
- **Stem type**: {stem_type}
  - vocals: single-pitch monophonic melody (human voice). No overlapping notes. Typical range C3-C6 (MIDI 48-84).
  - bass: low-frequency foundation. May have sustained notes and some overlap with other instruments but itself is monophonic.
  - drums: percussion, typically MIDI channel 10. Not applicable here.
  - other: mixed accompaniment, may be polyphonic.

## Diagnostic Report
{diagnostic_context}
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
"""
    return prompt


def generate_fix_instructions(diagnostic: MidiDiagnostic,
                              stem_type: str = "vocals",
                              reference_info: str = "") -> dict:
    """
    Generate fix instructions by calling LLM with diagnostic context.

    Args:
        diagnostic: The diagnostic report.
        stem_type: 'vocals', 'bass', 'other', or 'drums'.
        reference_info: Optional reference info (e.g. ABC notation melody).

    Returns:
        Dict with fix instructions, or fallback defaults if LLM unavailable.
    """
    context = build_diagnostic_context(diagnostic)
    prompt = build_fix_prompt(context, stem_type, reference_info)

    try:
        import openai
        from pathlib import Path

        # Try to use OpenAI API
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("DASHSCOPE_API_KEY")
        base_url = os.environ.get("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        model = os.environ.get("OPENAI_MODEL") or os.environ.get("DEFAULT_MODEL", "qwen-plus")

        if api_key:
            print(f"  LLM: model={model}, base_url={base_url}")
            client = openai.OpenAI(api_key=api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a music transcription expert. Output only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )
            result = json.loads(response.choices[0].message.content)
            return result
    except Exception as e:
        print(f"  LLM judgment unavailable: {e}")

    # Fallback: rule-based judgment based on stem type
    return _rule_based_fallback(diagnostic, stem_type)


def _rule_based_fallback(diagnostic: MidiDiagnostic, stem_type: str) -> dict:
    """Rule-based fallback fix instructions when LLM is unavailable."""
    fixes = []

    if stem_type == "vocals":
        # Always merge overlaps for monophonic source
        if diagnostic.overlap_rate > 0.1:
            fixes.append({
                "type": "merge_overlap",
                "description": f"Merge {diagnostic.overlap_rate:.0%} overlapping notes into single notes per timepoint",
                "params": {"strategy": "keep_highest_velocity"},
                "priority": "high",
            })

        # Merge fragment chains
        if diagnostic.chain_count_2plus > 10:
            fixes.append({
                "type": "merge_fragments",
                "description": f"Merge {diagnostic.chain_count_2plus} same-pitch fragment chains into sustained notes",
                "params": {"max_gap_sec": 0.5},
                "priority": "high",
            })

        # Remove out-of-range notes
        out_of_range = sum(c for p, c in diagnostic.pitch_counts.items()
                          if p < 48 or p > 84)
        if out_of_range > 0:
            pct = out_of_range / diagnostic.note_count * 100
            fixes.append({
                "type": "remove_out_of_range",
                "description": f"Remove {out_of_range} notes ({pct:.0f}%) outside C3-C6 range",
                "params": {"min_pitch": 48, "max_pitch": 84},
                "priority": "high",
            })

        # Velocity normalization
        if diagnostic.velocity_stats.get("min", 127) < 40 or diagnostic.velocity_stats.get("max", 0) > 110:
            fixes.append({
                "type": "normalize_velocity",
                "description": "Normalize velocity to 40-110 range",
                "params": {"min": 40, "max": 110},
                "priority": "low",
            })

        # BPM estimation
        if diagnostic.bpm > 200 or diagnostic.bpm < 50:
            fixes.append({
                "type": "estimate_bpm",
                "description": f"BPM {diagnostic.bpm} is likely wrong (fragmentation artifact). Re-estimate after merge.",
                "params": {"expected_range": [50, 160]},
                "priority": "medium",
            })

    return {
        "summary": f"Rule-based fallback for {stem_type} stem. {len(fixes)} fixes identified.",
        "fixes": fixes,
        "estimated_clean_note_count": diagnostic.note_count - out_of_range if stem_type == "vocals" else diagnostic.note_count,
    }


def apply_fixes(midi_path: str, fix_instructions: dict, output_path: str) -> str:
    """
    Apply fix instructions to a MIDI file and produce a cleaned version.

    Args:
        midi_path: Input MIDI file.
        fix_instructions: Dict from generate_fix_instructions().
        output_path: Output cleaned MIDI file.

    Returns:
        Path to cleaned MIDI file.
    """
    import pretty_midi

    pm = pretty_midi.PrettyMIDI(midi_path)
    if not pm.instruments:
        return None

    notes = sorted(pm.instruments[0].notes, key=lambda n: n.start)
    original_count = len(notes)

    for fix in fix_instructions.get("fixes", []):
        fix_type = fix["type"]

        if fix_type == "merge_overlap":
            # Merge overlapping notes: keep highest velocity at each timepoint
            notes = _merge_overlapping_notes(notes)

        elif fix_type == "merge_fragments":
            max_gap = fix["params"].get("max_gap_sec") or fix["params"].get("max_gap_seconds", 0.5)
            notes = _merge_fragment_chains(notes, max_gap)

        elif fix_type == "remove_out_of_range":
            min_p = fix["params"].get("min_pitch", 48)
            max_p = fix["params"].get("max_pitch", 84)
            notes = [n for n in notes if min_p <= n.pitch <= max_p]

        elif fix_type == "normalize_velocity":
            min_v = fix["params"].get("min") or fix["params"].get("target_min", 40)
            max_v = fix["params"].get("max") or fix["params"].get("target_max", 110)
            for n in notes:
                n.velocity = max(min_v, min(max_v, n.velocity))

    # Rebuild MIDI
    pm.instruments[0].notes = notes

    if "bpm" in fix_instructions:
        pm.instruments[0].program = fix_instructions.get("bpm", {}).get("program", pm.instruments[0].program)

    pm.write(output_path)
    print(f"  Fixed: {original_count} → {len(notes)} notes")
    return output_path


def _merge_overlapping_notes(notes: list) -> list:
    """Merge overlapping notes: at each timepoint, keep only the highest-velocity note."""
    if not notes:
        return []

    # Group by time intervals
    import numpy as np
    all_times = sorted(set([n.start for n in notes] + [n.end for n in notes]))

    merged = []
    for i in range(len(all_times) - 1):
        t_start = all_times[i]
        t_end = all_times[i + 1]
        if t_end - t_start < 0.001:
            continue

        # Find notes active in this interval
        active = [n for n in notes if n.start <= t_start and n.end >= t_end]
        if not active:
            continue

        # Keep highest velocity
        best = max(active, key=lambda n: n.velocity)
        merged.append(pretty_midi.Note(
            velocity=best.velocity,
            pitch=best.pitch,
            start=t_start,
            end=t_end,
        ))

    # Re-merge consecutive same-pitch notes
    if not merged:
        return []

    final = [merged[0]]
    for n in merged[1:]:
        if n.pitch == final[-1].pitch and abs(n.start - final[-1].end) < 0.05:
            final[-1].end = n.end
            final[-1].velocity = max(final[-1].velocity, n.velocity)
        else:
            final.append(n)

    return final


def _merge_fragment_chains(notes: list, max_gap: float = 0.5) -> list:
    """Merge consecutive same-pitch fragments within max_gap seconds."""
    if not notes:
        return []

    notes_sorted = sorted(notes, key=lambda n: n.start)
    merged = [notes_sorted[0]]

    for n in notes_sorted[1:]:
        last = merged[-1]
        gap = n.start - last.end
        if n.pitch == last.pitch and gap <= max_gap and gap > -0.01:
            # Merge: extend duration
            new_end = max(last.end, n.end)
            new_dur = new_end - last.start
            if new_dur < 0.01:
                new_dur = 0.01
            merged[-1] = pretty_midi.Note(
                velocity=max(last.velocity, n.velocity),
                pitch=last.pitch,
                start=last.start,
                end=new_end,
            )
        else:
            merged.append(n)

    return merged


def fix_midi(midi_path: str, stem_type: str = "vocals",
             output_path: str | None = None,
             reference_info: str = "") -> str:
    """
    Full fix pipeline: analyze → LLM judgment → apply fixes.

    Args:
        midi_path: Input MIDI file.
        stem_type: 'vocals', 'bass', 'other'.
        output_path: Output path (default: same name + _fixed.mid).
        reference_info: Optional reference info for LLM.

    Returns:
        Path to cleaned MIDI file.
    """
    if output_path is None:
        base = os.path.splitext(midi_path)[0]
        output_path = f"{base}_fixed.mid"

    # Step 1: Analyze
    from core.midi_analysis import analyze_midi
    diagnostic = analyze_midi(midi_path)
    print(f"  Diagnostic report:")
    print(diagnostic.to_report())
    print()

    # Step 2: LLM judgment (with fallback)
    fix_instructions = generate_fix_instructions(diagnostic, stem_type, reference_info)
    print(f"  Fix instructions: {json.dumps(fix_instructions, indent=2, ensure_ascii=False)}")
    print()

    # Step 3: Apply fixes
    result = apply_fixes(midi_path, fix_instructions, output_path)
    return result


def fix_midi_to_score(midi_path: str, stem_type: str = "vocals",
                      output_dir: str | None = None,
                      reference_info: str = "",
                      quantize_style: str = "clean_score") -> dict:
    """
    Full pipeline: fix MIDI → ABC → LLM quantization → clean MIDI.

    Args:
        midi_path: Input MIDI file.
        stem_type: 'vocals', 'bass', 'other'.
        output_dir: Directory for intermediate files (default: same dir as midi_path).
        reference_info: Optional reference info for MIDI fix step.
        quantize_style: LLM quantization style.

    Returns:
        Dict with paths to all intermediate and final outputs.
    """
    base = os.path.splitext(midi_path)[0]
    if output_dir is None:
        output_dir = os.path.dirname(base) or "."

    fixed_mid = os.path.join(output_dir, f"{os.path.basename(base)}_fixed.mid")
    abc_raw = os.path.join(output_dir, f"{os.path.basename(base)}_raw.abc")
    abc_quant = os.path.join(output_dir, f"{os.path.basename(base)}_quantized.abc")
    quantized_mid = os.path.join(output_dir, f"{os.path.basename(base)}_quantized.mid")

    from core.midi_analysis import analyze_midi
    from core.midi_to_abc import midi_to_abc, abc_to_midi, read_abc, write_abc
    from core.abc_quantize import quantize_abc, extract_key_from_abc, validate_abc

    print("=" * 50)
    print("Stage 1: MIDI fix (analysis → LLM → tool)")
    print("=" * 50)
    fixed_mid = fix_midi(midi_path, stem_type, fixed_mid, reference_info)
    if not fixed_mid:
        return None

    print("=" * 50)
    print("Stage 2: MIDI → ABC")
    print("=" * 50)
    abc_path = midi_to_abc(fixed_mid, abc_raw)
    if not abc_path:
        return {"fixed_mid": fixed_mid}

    abc_text = read_abc(abc_path)
    key = extract_key_from_abc(abc_text)
    print(f"  ABC key: {key}, size: {len(abc_text)} bytes")
    print()

    print("=" * 50)
    print("Stage 3: LLM tonal quantization")
    print("=" * 50)
    quantized = quantize_abc(abc_text, key=key, style=quantize_style)
    if not quantized:
        print("  LLM quantization failed, using raw ABC")
        quantized = abc_text

    quantized_path = write_abc(quantized, abc_quant)
    print(f"  Quantized ABC: {quantized_path}, size: {len(quantized)} bytes")
    print()

    print("=" * 50)
    print("Stage 4: ABC → MIDI")
    print("=" * 50)
    final_mid = abc_to_midi(quantized_path, quantized_mid)

    # Compare results
    print()
    print("=" * 50)
    print("Comparison")
    print("=" * 50)
    for path, label in [
        (midi_path, "Original"),
        (fixed_mid, "Fixed"),
        (final_mid, "Quantized"),
    ]:
        if path and os.path.exists(path):
            d = analyze_midi(path)
            print(f"  {label} ({d.note_count} notes): overlap={d.overlap_rate:.0%}, "
                  f"chains(2+)={d.chain_count_2plus}, pitch={d.pitch_range}")

    return {
        "fixed_mid": fixed_mid,
        "abc_raw": abc_path,
        "abc_quantized": quantized_path,
        "quantized_mid": final_mid,
    }
