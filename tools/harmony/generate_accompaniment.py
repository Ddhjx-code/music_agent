"""
Accompaniment generation tool.

Generates piano accompaniment patterns from a chord progression
in multiple styles: classical (Alberti bass), romantic (arpeggios), pop (block chords).
Features: dynamic accents, humanized timing, style-specific phrasing.
"""

import re
import random

import musicpy as mp

# RNG seed for reproducibility
random.seed(42)

# Map alteration markers to interval adjustments (original → modified semitones).
# Applied as post-processing on base intervals.
_ALTERATIONS = {
    '#5': {7: 8},    # raised 5th
    'b5': {7: 6},    # lowered 5th
    '#11': {17: 18}, # raised 11th
    'b11': {17: 16}, # lowered 11th
    '#9': {14: 15},  # raised 9th
    'b9': {14: 13},  # lowered 9th
    '#13': {21: 22}, # raised 13th
    'b13': {21: 20}, # lowered 13th
}


def _apply_alterations(intervals: list[int], quality: str) -> list[int]:
    """Apply alteration markers like #11, b5, #9 to interval list."""
    result = list(intervals)
    for marker, mapping in _ALTERATIONS.items():
        if marker in quality:
            # Replace matching intervals, add altered value if target not present
            src, dst = next(iter(mapping.items()))
            if src in result:
                result = [dst if i == src else i for i in result]
            else:
                # Add the altered interval (e.g., #11=18 for maj13#11)
                result = result + [dst]
    return sorted(result)


# Map chord names to note components with full extended intervals.
# Handles: Cmajor, Cminor, Cmaj7, C7, Cdim, Caug, Csus2, Csus4, etc.
# Also handles musicpy output like "Am13 omit G sort as [3, 1, 2, 5, 4, 6]"
def _parse_chord_name(chord_str: str) -> tuple[str, list[int]]:
    """
    Parse a chord name into (root, intervals).

    Returns full extended intervals so accompaniment patterns can include
    7ths, 9ths, 11ths, 13ths, 6ths, sus tones, etc.

    Returns (root_note, chord_intervals) where intervals are semitone offsets.
    """
    chord_str = chord_str.strip()

    # Handle special cases
    if chord_str in ('rest', 'unknown', ''):
        return 'C', [0, 4, 7]

    # Extract root — handle 'note G4' format and sharp/flat roots
    match = re.match(r'^(?:note\s+)?([A-G][#b]?)(.*)', chord_str)
    if not match:
        return 'C', [0, 4, 7]

    root = match.group(1)
    quality_raw = match.group(2).lower().strip()

    # Strip noise: slash bass notes, omit clauses, sort directives
    quality = re.sub(r'/[A-G][#b]?\s*$', '', quality_raw)  # trailing /X
    quality = re.sub(r'\s*sort\s+as\s+\[.*?\]', '', quality)
    quality = re.sub(r'\s*omit\s+\w+', '', quality)
    quality = quality.strip()

    # ---- Quality detection (most specific first) ----
    # Each returns a list of semitone intervals from the root.

    # Major family (no extensions) — no alterations apply
    if quality in ('major', 'maj', ''):
        return root, [0, 4, 7]

    # 6/69 chords — must check before 7/9/11/13 to avoid false match on '6'
    if quality == '69' or quality == '6add9':
        return root, _apply_alterations([0, 4, 7, 9, 14], quality)
    if quality == '6':
        return root, _apply_alterations([0, 4, 7, 9], quality)

    # add9 — adds 9th but no 7th
    if quality == 'add9':
        return root, _apply_alterations([0, 4, 7, 14], quality)

    # Major 7th family: maj7, maj9, maj11, maj13
    if quality.startswith('maj'):
        if '13' in quality:
            return root, _apply_alterations([0, 4, 7, 11, 14, 21], quality)
        if '11' in quality:
            return root, _apply_alterations([0, 4, 7, 11, 17], quality)
        if '9' in quality:
            return root, _apply_alterations([0, 4, 7, 11, 14], quality)
        return root, _apply_alterations([0, 4, 7, 11], quality)  # maj7

    # Minor family: m, min, m7, m9, m11, m13, min7, minor7
    if quality == 'm':
        return root, _apply_alterations([0, 3, 7], quality)
    if quality.startswith('min') or quality.startswith('minor'):
        if '13' in quality:
            return root, _apply_alterations([0, 3, 7, 10, 14, 21], quality)
        if '11' in quality:
            return root, _apply_alterations([0, 3, 7, 10, 17], quality)
        if '9' in quality:
            return root, _apply_alterations([0, 3, 7, 10, 14], quality)
        if '7' in quality:
            return root, _apply_alterations([0, 3, 7, 10], quality)
        return root, _apply_alterations([0, 3, 7], quality)
    if quality.startswith('m'):
        # mx patterns: m7, m9, m11, m13
        if '13' in quality:
            return root, _apply_alterations([0, 3, 7, 10, 14, 21], quality)
        if '11' in quality:
            return root, _apply_alterations([0, 3, 7, 10, 17], quality)
        if '9' in quality:
            return root, _apply_alterations([0, 3, 7, 10, 14], quality)
        if '7' in quality:
            return root, _apply_alterations([0, 3, 7, 10], quality)
        return root, _apply_alterations([0, 3, 7], quality)

    # Diminished
    if 'dim' in quality:
        return root, _apply_alterations([0, 3, 6], quality)

    # Augmented
    if 'aug' in quality:
        if '7' in quality or '9' in quality:
            return root, _apply_alterations([0, 4, 8, 10], quality)  # aug7
        return root, _apply_alterations([0, 4, 8], quality)

    # Suspended family: sus2, sus4, 7sus2, 7sus4, 9sus4, 13sus2, 13sus4
    if 'sus4' in quality:
        if '13' in quality:
            return root, _apply_alterations([0, 5, 7, 10, 14, 21], quality)  # 13sus4
        if '7' in quality or '9' in quality or '11' in quality:
            return root, _apply_alterations([0, 5, 7, 10], quality)  # 7sus4
        return root, _apply_alterations([0, 5, 7], quality)
    if 'sus2' in quality:
        if '13' in quality:
            return root, _apply_alterations([0, 2, 7, 10, 14, 21], quality)  # 13sus2
        if '7' in quality or '9' in quality or '11' in quality:
            return root, _apply_alterations([0, 2, 7, 10], quality)  # 7sus2
        return root, _apply_alterations([0, 2, 7], quality)

    # Extended dominant: 7, 9, 11, 13
    if '13' in quality:
        return root, _apply_alterations([0, 4, 7, 10, 14, 21], quality)
    if '11' in quality:
        return root, _apply_alterations([0, 4, 7, 10, 14, 17], quality)
    if '9' in quality:
        return root, _apply_alterations([0, 4, 7, 10, 14], quality)
    if '7' in quality:
        return root, _apply_alterations([0, 4, 7, 10], quality)

    return root, _apply_alterations([0, 4, 7], quality)  # Default major triad


def _root_to_base_octave(root: str) -> int:
    """Determine a good base octave for accompaniment from root note."""
    root_map = {'C': 3, 'D': 3, 'E': 3, 'F': 2, 'G': 2, 'A': 2, 'B': 2}
    return root_map.get(root, 3)


def _accent_for_position(note_idx_in_measure: int, pattern_len: int, measure_num: int) -> float:
    """
    Return velocity multiplier for 4/4 time accents.

    4/4 accent pattern:
    - Beat 1 (strong): 1.0
    - Beat 3 (medium): 0.75
    - Beats 2, 4 (weak): 0.55
    - Off-beats: 0.45
    - Even measures: slightly softer (phrase structure)
    """
    beat = note_idx_in_measure / (pattern_len / 4.0)  # Approximate beat position
    if beat < 0.5:  # Beat 1 (downbeat)
        base = 1.0
    elif 1.0 <= beat < 1.5:  # Beat 3
        base = 0.75
    elif 0.5 <= beat < 1.0 or 1.5 <= beat < 2.0:  # Beats 2 or 4
        base = 0.55
    else:  # Off-beats
        base = 0.45

    # Phrase structure: every other measure slightly softer
    phrase = 0.85 if measure_num % 2 == 0 else 1.0
    return base * phrase


def _humanize_timing(timing: float, jitter: float = 0.02) -> float:
    """Add subtle timing variation to simulate human playing."""
    return max(0.05, timing + random.uniform(-jitter, jitter))


def _make_notes(root: str, intervals: list[int], octave: int) -> list[mp.note]:
    """Create note objects from root, intervals, and octave."""
    midi_to_name = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    root_idx = midi_to_name.index(root) if root in midi_to_name else 0
    notes = []
    for interval in intervals:
        midi = (octave + 1) * 12 + (root_idx + interval) % 12
        note_name = midi_to_name[midi % 12]
        note_octave = midi // 12 - 1
        notes.append(mp.note(note_name, note_octave, duration=0.25))
    return notes


class GenerateAccompanimentTool:
    """Generate piano accompaniment from a chord progression."""

    name = "generate_accompaniment"
    description = (
        "Generate piano accompaniment from a chord progression. "
        "Supports classical (Alberti bass/broken chords), "
        "romantic (wide arpeggios), and pop (block chords + octave bass) styles. "
        "Parameters: style, pattern, voicing (closed/open), density (sparse/medium/dense)."
    )

    def run(self, harmony: list[dict], style: str = 'classical',
            pattern: str = 'broken_chord', voicing: str = 'closed',
            density: str = 'medium', total_measures: int = None) -> mp.chord:
        """
        Generate accompaniment for a chord progression.

        Args:
            harmony: List of {measure, chord} dicts from analyze_harmony.
            style: 'classical', 'romantic', or 'pop'.
            pattern: 'broken_chord', 'arpeggio', or 'block_chord'.
            voicing: 'closed' or 'open'.
            density: 'sparse', 'medium', or 'dense'.
            total_measures: Total number of measures to fill (extends last chord
                           if more than harmony entries).

        Returns:
            A chord object containing the accompaniment notes.
        """
        if not harmony:
            return mp.chord([])

        # Map style to pattern if not explicitly set
        if pattern == 'broken_chord' and style == 'romantic':
            pattern = 'arpeggio'
        elif pattern == 'broken_chord' and style == 'pop':
            pattern = 'block_chord'

        # Build full harmony list — extend last chord if total_measures given
        full_harmony = list(harmony)
        if total_measures and len(full_harmony) < total_measures:
            last = full_harmony[-1].copy()
            for m in range(len(full_harmony) + 1, total_measures + 1):
                last['measure'] = m
                full_harmony.append(last)

        all_notes = []
        all_intervals = []
        for entry in full_harmony:
            chord_str = entry.get('chord', 'Cmajor')
            measure = entry.get('measure', 1)

            root, chord_intervals = _parse_chord_name(chord_str)
            octave = _root_to_base_octave(root)

            if pattern == 'arpeggio':
                notes, timings = self._make_arpeggio(root, chord_intervals, octave, voicing, density, measure)
            elif pattern == 'block_chord':
                notes, timings = self._make_block_chord(root, chord_intervals, octave, voicing, density, measure)
            else:
                notes, timings = self._make_broken_chord(root, chord_intervals, octave, density, measure)

            all_notes.extend(notes)
            all_intervals.extend(timings)

        if not all_intervals:
            all_intervals = [0]
        return mp.chord(all_notes, interval=all_intervals)

    def _make_arpeggio(self, root, intervals, base_octave, voicing, density, measure_num=1):
        """Wide arpeggio spanning 2+ octaves, fills one full measure.
        Returns (notes, timing_intervals)."""
        midi_to_name = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        notes = []
        timings = []

        extended = list(intervals)
        if voicing == 'open':
            extended = intervals + [i + 12 for i in intervals]

        sweeps = {'sparse': 1, 'medium': 2, 'dense': 3}.get(density, 2)
        beats = 4.0
        sweep_duration = beats / sweeps

        for sweep in range(sweeps):
            octave_offset = sweep * 12
            note_dur = sweep_duration / len(extended)
            for j, interval in enumerate(extended):
                midi = (base_octave + 1) * 12 + interval + octave_offset
                name = midi_to_name[midi % 12]
                octave = midi // 12 - 1
                # Root note gets accent
                vel = 90 if j == 0 else 70
                acc = _accent_for_position(j + sweep * len(extended), len(extended) * sweeps, measure_num)
                n = mp.note(name, octave, duration=note_dur, volume=max(45, min(127, int(vel * acc))))
                n.interval = _humanize_timing(note_dur)
                notes.append(n)
                timings.append(note_dur)

        return notes, timings

    def _make_block_chord(self, root, intervals, base_octave, voicing, density, measure_num=1):
        """Block chords with octave bass. Returns (notes, timing_intervals)."""
        notes = []
        timings = []
        # Bass note (octave below) — emphasized
        bass_midi = (base_octave) * 12 + (intervals[0] % 12)
        bass_name = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'][bass_midi % 12]
        bass_octave = bass_midi // 12 - 1
        acc = _accent_for_position(0, 8, measure_num)
        bass_vol = max(50, min(127, int(95 * acc)))
        notes.append(mp.note(bass_name, bass_octave, duration=2.0, volume=bass_vol))
        timings.append(0.0)

        # Chord tones (played together as block)
        chord_notes = _make_notes(root, intervals, base_octave)
        for j, cn in enumerate(chord_notes):
            ch_acc = _accent_for_position(2 + j, 8, measure_num)
            ch_vol = max(50, min(127, int(80 * ch_acc)))
            n = mp.note(cn.name, cn.num, duration=2.0, volume=ch_vol)
            n.interval = 0.0
            notes.append(n)
            timings.append(0.0)

        # Add octave doubling for dense
        if density == 'dense':
            for cn in chord_notes:
                n = mp.note(cn.name, cn.num + 1, duration=2.0, volume=65)
                n.interval = 0.0
                notes.append(n)
                timings.append(0.0)

        return notes, timings

    def _make_broken_chord(self, root, intervals, base_octave, density, measure_num=1):
        """Alberti bass style, fills one full 4-beat measure.
        Returns (notes, timing_intervals)."""
        if len(intervals) < 3:
            intervals = [0, 4, 7]  # Force major triad

        notes = []
        timings = []

        if len(intervals) >= 4:
            pattern = list(range(len(intervals)))
        else:
            pattern = [0, 2, 1, 2]

        pattern_len = len(pattern)
        beats = 4.0
        eighth_note = 0.5
        total_eighths = int(beats / eighth_note)

        for i in range(total_eighths):
            idx = pattern[i % pattern_len]
            interval = intervals[idx % len(intervals)]
            midi = (base_octave + 1) * 12 + interval
            name = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'][midi % 12]
            octave = midi // 12 - 1

            # Accent pattern: first beat strong, third medium, rest weak
            acc = _accent_for_position(i, total_eighths, measure_num)
            # Root/5th notes slightly louder (bass emphasis)
            base_vol = 85 if idx % len(intervals) < 2 else 70
            vol = max(50, min(127, int(base_vol * acc)))

            notes.append(mp.note(name, octave, duration=eighth_note, volume=vol))
            timings.append(eighth_note)

        return notes, timings
