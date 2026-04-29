"""
MIDI ↔ ABC notation conversion.

MIDI → ABC: reads MIDI via mido, always outputs K:C (no key signature)
with explicit accidentals so every pitch is unambiguous.

ABC → MIDI: uses abc2midi CLI (brew install abcmidi).
Sheet music:  uses abcm2ps CLI (brew install abcm2ps).
"""

import os
import subprocess

from mido import MidiFile


def midi_to_abc(midi_path: str, abc_path: str) -> str | None:
    """
    Convert MIDI file to ABC notation with K:C (no key signature).

    Always uses K:C so every pitch has an explicit accidental.  This avoids
    the ambiguity of midi2abc which auto-detects a key and uses implicit
    sharps/flats that confuse downstream readers (especially LLMs).

    Multi-track MIDI → ABC with multiple voices (V:1, V:2, ...).

    Args:
        midi_path: Input MIDI file.
        abc_path: Output ABC file path.

    Returns:
        Path to ABC file, or None on failure.
    """
    mid = MidiFile(midi_path)

    try:
        bpm = _extract_bpm(midi_path)
        voices = []
        for i, track in enumerate(mid.tracks):
            events = _parse_track_events(track, mid.ticks_per_beat)
            if events:
                voices.append((i, events))

        if not voices:
            print("  Error: no notes found in MIDI")
            return None

        return _write_multi_voice_abc(abc_path, midi_path, bpm, voices)
    except Exception as e:
        print(f"  Error: cannot convert MIDI to ABC: {e}")
        return None


# ── MIDI parsing ──────────────────────────────────────────────────────

def _parse_track_events(track, tpb: int) -> list[tuple[float, float, int]]:
    """Parse a single MIDI track into list of (start_beats, duration_beats, midi_note)."""
    active = {}  # note -> onset_tick
    abs_tick = 0
    all_events = []

    for msg in track:
        abs_tick += msg.time

        if msg.type == 'note_on' and msg.velocity > 0:
            active[msg.note] = abs_tick
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            if msg.note in active:
                onset = active.pop(msg.note)
                dur_beats = (abs_tick - onset) / tpb
                start_beats = onset / tpb
                all_events.append((start_beats, dur_beats, msg.note))

    all_events.sort(key=lambda x: (x[0], x[2]))
    return all_events


def _parse_midi_events(midi_path: str) -> list[tuple[float, float, int]]:
    """Legacy: parse all tracks merged into single voice."""
    mid = MidiFile(midi_path)
    all_events = []
    for track in mid.tracks:
        all_events.extend(_parse_track_events(track, mid.ticks_per_beat))
    all_events.sort(key=lambda x: (x[0], x[2]))
    return all_events


def _extract_bpm(midi_path: str) -> float:
    """Extract BPM from MIDI tempo meta messages."""
    mid = MidiFile(midi_path)
    for track in mid.tracks:
        for msg in track:
            if msg.type == 'set_tempo':
                return 60000000 / msg.tempo
    return 120.0


# ── ABC writing ──────────────────────────────────────────────────────

# Map MIDI note number → ABC pitch letter with explicit sharp
_ABC_PITCH = ['C', '^C', 'D', '^D', 'E', 'F', '^F', 'G', '^G', 'A', '^A', 'B']


def _midi_to_abc_pitch(midi_note: int) -> str:
    """Convert MIDI note number to ABC pitch string (K:C).

    abc2midi interprets:
      C,, = C2 (MIDI 36), C, = C3 (MIDI 48), C = C4 (MIDI 60),
      c = C5 (MIDI 72), c' = C6 (MIDI 84), c'' = C7 (MIDI 96)
    """
    name = _ABC_PITCH[midi_note % 12]
    octave = midi_note // 12  # C3=4, C4=5, C5=6, C6=7

    if octave < 5:
        return name + "," * (5 - octave)
    elif octave == 5:
        return name
    else:
        return name.lower() + "'" * (octave - 6)


def _events_to_voice_lines(events: list[tuple[float, float, int]], bar_len: int = 8) -> list[str]:
    """Convert a list of (start_beats, dur_beats, midi_note) to ABC measure strings.

    Uses L:1/8, so 1 beat = 2 ABC units, 1 bar = 8 ABC units (4/4).
    """
    if not events:
        return []

    converted = []
    for start, dur, note in events:
        start_8ths = max(0, int(round(start * 2)))
        dur_8ths = max(1, int(round(dur * 2)))
        pitch = _midi_to_abc_pitch(note)
        converted.append((start_8ths, dur_8ths, pitch))

    last_start, last_dur, _ = converted[-1]
    total_8ths = last_start + last_dur
    total_8ths = ((total_8ths + bar_len - 1) // bar_len) * bar_len

    # Per-8th occupancy
    occupancy = [set() for _ in range(total_8ths)]
    for s8, d8, pitch in converted:
        for t in range(s8, min(s8 + d8, total_8ths)):
            occupancy[t].add(pitch)

    measures = []
    bar_parts = []
    bar_dur = 0
    pos = 0

    while pos < total_8ths:
        if bar_dur >= bar_len:
            measures.append(''.join(bar_parts))
            bar_parts = []
            bar_dur = 0

        current_pitches = occupancy[pos]
        remaining = bar_len - bar_dur

        if not current_pitches:
            run_len = 0
            while (pos + run_len < total_8ths
                   and not occupancy[pos + run_len]
                   and run_len < remaining):
                run_len += 1
            if run_len == 0:
                run_len = 1
            bar_parts.append(_dur_str(run_len, is_rest=True))
        else:
            run_len = 1
            while (pos + run_len < total_8ths
                   and occupancy[pos + run_len] == current_pitches
                   and run_len < remaining):
                run_len += 1

            if len(current_pitches) == 1:
                pitch = next(iter(current_pitches))
                bar_parts.append(pitch + _dur_str(run_len))
            else:
                chord_str = '[' + ''.join(sorted(current_pitches)) + ']'
                bar_parts.append(chord_str + _dur_str(run_len))

        bar_dur += run_len
        pos += run_len

    if bar_parts:
        measures.append(''.join(bar_parts))

    return measures


def _write_multi_voice_abc(path: str, midi_path: str, bpm: float,
                           voices: list[tuple[int, list]]) -> str | None:
    """Write multi-voice ABC file using [V:N] inline voice syntax."""
    lines = [
        "X: 1",
        f"T: from {midi_path}",
        "M: 4/4",
        "L: 1/8",
        f"Q:1/4={int(round(bpm))}",
        "K:C",
    ]

    for i, (_track_idx, events) in enumerate(voices):
        voice_num = i + 1
        measures = _events_to_voice_lines(events)

        if not measures:
            continue

        # Declare voices at top
        if i == 0:
            lines.append(f"V:{voice_num} clef=treble")
        else:
            lines.append(f"V:{voice_num} clef=bass")

        # Write measures with inline voice switches
        for m in measures:
            lines.append(f"[V:{voice_num}] {m} |")

    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w") as f:
        f.write('\n'.join(lines) + '\n')
    return path




def _dur_str(units: int, is_rest: bool = False) -> str:
    """Convert duration in 8th-note units to ABC duration suffix.

    With L:1/8:  1=8th (empty suffix), 2=quarter, 3=dotted-quarter,
                  4=half, 6=dotted-half, 8=whole.
    Multipliers >1 use the number directly: 3=3 eighths, 5=5 eighths, etc.
    """
    if is_rest:
        base = 'z'
    else:
        if units == 1:
            return ''
        base = ''

    if units == 2:
        return base + '2'
    elif units == 3:
        return base + '3'
    elif units == 4:
        return base + '4'
    elif units == 6:
        return base + '6'
    elif units == 8:
        return base + '8'
    else:
        return base + str(units)


# ── ABC → MIDI (uses abc2midi CLI) ──────────────────────────────────

def abc_to_midi(abc_path: str, midi_path: str) -> str | None:
    """Convert ABC notation to MIDI file via abc2midi."""
    tool = _find_tool("abc2midi")
    if not tool:
        print("  Error: abc2midi not found. Install: brew install abcmidi")
        return None

    result = subprocess.run(
        [tool, abc_path, "-o", midi_path],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0 or not os.path.exists(midi_path):
        print(f"  Error: abc2midi failed: {result.stderr.strip()}")
        return None

    return midi_path


def abc_to_png(abc_path: str, png_path: str) -> str | None:
    """Convert ABC notation to sheet music PNG via abcm2ps."""
    tool = _find_tool("abcm2ps")
    if not tool:
        print("  Error: abcm2ps not found. Install: brew install abcm2ps")
        return None

    ps_dir = os.path.dirname(png_path) or "."
    ps_base = os.path.splitext(os.path.basename(png_path))[0]
    ps_output = os.path.join(ps_dir, f"{ps_base}.ps")

    result = subprocess.run(
        [tool, abc_path, "-O", ps_output],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0 or not os.path.exists(ps_output):
        print(f"  Error: abcm2ps failed: {result.stderr.strip()}")
        return None

    gs = _find_tool("gs")
    if gs:
        subprocess.run(
            [gs, "-dSAFER", "-dBATCH", "-dNOPAUSE", "-r150",
             "-sDEVICE=png16m", f"-sOutputFile={png_path}", ps_output],
            capture_output=True, timeout=30,
        )
    else:
        sips = _find_tool("sips")
        if sips:
            subprocess.run(
                [sips, "-s", "format", "png", ps_output, "--out", png_path],
                capture_output=True, timeout=30,
            )
        else:
            print("  Warning: no PS→PNG converter found (gs or sips)")
            return None

    if os.path.exists(png_path):
        return png_path
    return None


def read_abc(path: str) -> str | None:
    """Read ABC file contents as string."""
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return f.read()


def write_abc(text: str, path: str) -> str | None:
    """Write ABC notation string to file."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    return path if os.path.exists(path) else None


def _find_tool(name: str) -> str | None:
    """Find a CLI tool in PATH."""
    for d in os.environ.get("PATH", "").split(os.pathsep):
        p = os.path.join(d, name)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None
