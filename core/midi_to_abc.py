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
    """Convert events to ABC measure strings.

    Uses L:1/8.  Each bar is self-contained — no ties across bar boundaries.
    Notes crossing bar boundaries are split into separate notes per bar.
    Every bar is filled to exactly 8 units using standard ABC durations.
    """
    if not events:
        return []

    UNIT_PER_BEAT = 2  # At L:1/8, quarter note = 2 units
    BAR_LEN = 8        # 4/4 bar = 8 eighth-notes

    def _emit_single(units: int, pitch_str: str, is_rest: bool = False) -> str:
        """Emit a single note/rest with a standard ABC duration suffix."""
        base = 'z' if is_rest else pitch_str
        return {
            1: base, 2: base + '2', 3: base + '3', 4: base + '4',
            6: base + '6', 8: base + '8',
        }.get(units, base)

    def _emit_tied(units: int, pitch_str: str, is_rest: bool = False) -> str:
        """Emit duration as sum of standard values, joined by ties (or spaces for rests)."""
        if units <= 0:
            return 'z'
        # Greedy decomposition into standard values
        STANDARD_DURS = [8, 6, 4, 3, 2, 1]
        parts = []
        remaining = units
        while remaining > 0:
            for d in STANDARD_DURS:
                if d <= remaining:
                    parts.append(d)
                    remaining -= d
                    break
            else:
                break  # safety
        if len(parts) == 1:
            return _emit_single(parts[0], pitch_str, is_rest)
        if is_rest:
            return ' '.join(_emit_single(p, pitch_str, True) for p in parts)
        return '-'.join(_emit_single(p, pitch_str, False) for p in parts)

    # Convert events and split at bar boundaries
    bar_events: dict[int, list[tuple[int, int, str]]] = {}
    for start, dur, note in events:
        start_u = max(0, int(round(start * UNIT_PER_BEAT)))
        dur_u = max(1, int(round(dur * UNIT_PER_BEAT)))
        pitch = _midi_to_abc_pitch(note)
        end_u = start_u + dur_u

        bar_idx = start_u // BAR_LEN
        pos = start_u
        while pos < end_u:
            bar_end = (bar_idx + 1) * BAR_LEN
            seg_end = min(end_u, bar_end)
            seg_dur = seg_end - pos
            if seg_dur > 0:
                bar_events.setdefault(bar_idx, []).append((pos, seg_dur, pitch))
            pos = seg_end
            bar_idx += 1

    last_bar_idx = max(bar_events.keys()) if bar_events else 0

    measures = []
    for bar_idx in range(last_bar_idx + 1):
        segs = bar_events.get(bar_idx, [])
        if not segs:
            measures.append('z8')
            continue

        bar_start = bar_idx * BAR_LEN
        occupancy = [set() for _ in range(BAR_LEN)]
        for su, du, pitch in segs:
            local = su - bar_start
            for t in range(local, min(local + du, BAR_LEN)):
                occupancy[t].add(pitch)

        bar_parts = []
        pos = 0
        while pos < BAR_LEN:
            current = occupancy[pos]
            if not current:
                run = 0
                while pos + run < BAR_LEN and not occupancy[pos + run]:
                    run += 1
                bar_parts.append(_emit_tied(run, 'z', is_rest=True))
                pos += run
            else:
                run = 1
                while pos + run < BAR_LEN and occupancy[pos + run] == current:
                    run += 1
                if len(current) == 1:
                    pitch = next(iter(current))
                    bar_parts.append(_emit_tied(run, pitch))
                else:
                    chord_str = '[' + ''.join(sorted(current)) + ']'
                    bar_parts.append(_emit_tied(run, chord_str))
                pos += run

        measures.append(' '.join(bar_parts))

    return measures


def _write_multi_voice_abc(path: str, midi_path: str, bpm: float,
                           voices: list[tuple[int, list]]) -> str | None:
    """Write multi-voice ABC file using voice-grouped format (abc2midi-friendly)."""
    header = [
        "X: 1",
        f"T: from {midi_path}",
        "M: 4/4",
        "L: 1/8",
        f"Q:1/4={int(round(bpm))}",
        "K:C",
    ]

    voice_measures = []
    for i, (_track_idx, events) in enumerate(voices):
        measures = _events_to_voice_lines(events)
        if not measures:
            continue
        clef = "treble" if i == 0 else "bass"
        voice_measures.append((i + 1, clef, measures))

    if not voice_measures:
        return None

    max_bars = max(len(m) for _, _, m in voice_measures)
    for idx, (vn, clef, measures) in enumerate(voice_measures):
        while len(measures) < max_bars:
            measures.append('z8')
        voice_measures[idx] = (vn, clef, measures)

    lines = header[:]
    for vn, clef, _ in voice_measures:
        lines.append(f"V:{vn} clef={clef}")

    for vn, _, measures in voice_measures:
        for m in measures:
            lines.append(f"[V:{vn}] {m} |")

    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w") as f:
        f.write('\n'.join(lines) + '\n')
    return path




def _dur_to_abc(units: int, pitch_str: str, is_rest: bool = False) -> str:
    """Convert duration in 1/16-note units to unambiguous ABC notation.

    With L:1/16:  4=quarter, 2=eighth, 8=half, 16=whole.
    Non-standard durations are split into tied notes.
    E.g. 5 sixteenths = pitch4 + pitch1 (quarter tied to sixteenth).

    This avoids the ambiguity where abc2midi interprets `c5` as C-octave-5
    rather than C with duration 5.
    """
    if units <= 0:
        return 'z'

    # Standard ABC duration values at L:1/16 (all unambiguous)
    # 1=sixteenth(/2), 2=eighth, 3=dotted-eighth(3/2), 4=quarter(2),
    # 6=dotted-quarter(3), 8=half(4), 12=dotted-half(6), 16=whole(8)
    def _single(u, p, rest):
        base = 'z' if rest else p
        return {
            1: base + '/2', 2: base, 3: base + '3/2', 4: base + '2',
            6: base + '3', 8: base + '4', 12: base + '6', 16: base + '8',
        }.get(u, f'{base}{u}')

    # Always split into standard durations
    parts = []
    remaining = units
    while remaining > 0:
        if remaining >= 16:
            parts.append(_single(16, pitch_str, is_rest)); remaining -= 16
        elif remaining >= 12:
            parts.append(_single(12, pitch_str, is_rest)); remaining -= 12
        elif remaining >= 8:
            parts.append(_single(8, pitch_str, is_rest)); remaining -= 8
        elif remaining >= 6:
            parts.append(_single(6, pitch_str, is_rest)); remaining -= 6
        elif remaining >= 4:
            parts.append(_single(4, pitch_str, is_rest)); remaining -= 4
        elif remaining >= 3:
            parts.append(_single(3, pitch_str, is_rest)); remaining -= 3
        elif remaining >= 2:
            parts.append(_single(2, pitch_str, is_rest)); remaining -= 2
        else:
            parts.append(_single(1, pitch_str, is_rest)); remaining -= 1

    return '-'.join(parts)


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
