"""
Accompaniment generation tool.

Generates piano accompaniment patterns from a chord progression
in multiple styles: classical (Alberti bass), romantic (arpeggios), pop (block chords).
"""

import re

import musicpy as mp


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
            density: str = 'medium') -> mp.chord:
        """
        Generate accompaniment for a chord progression.

        Args:
            harmony: List of {measure, chord} dicts from analyze_harmony.
            style: 'classical', 'romantic', or 'pop'.
            pattern: 'broken_chord', 'arpeggio', or 'block_chord'.
            voicing: 'closed' or 'open'.
            density: 'sparse', 'medium', or 'dense'.

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

        all_notes = []
        for entry in harmony:
            chord_str = entry.get('chord', 'Cmajor')
            measure = entry.get('measure', 1)

            root, intervals = _parse_chord_name(chord_str)
            octave = _root_to_base_octave(root)

            if pattern == 'arpeggio':
                notes = self._make_arpeggio(root, intervals, octave, voicing, density)
            elif pattern == 'block_chord':
                notes = self._make_block_chord(root, intervals, octave, voicing, density)
            else:
                notes = self._make_broken_chord(root, intervals, octave, density)

            all_notes.extend(notes)

        return mp.chord(all_notes)

    def _make_arpeggio(self, root, intervals, base_octave, voicing, density):
        """Wide arpeggio spanning 2+ octaves."""
        midi_to_name = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        notes = []
        sweeps = {'sparse': 1, 'medium': 2, 'dense': 3}.get(density, 2)

        # Build extended interval list for wide voicing
        extended = list(intervals)
        if voicing == 'open':
            extended = intervals + [i + 12 for i in intervals]

        for sweep in range(sweeps):
            octave_offset = sweep * 12
            for interval in extended:
                midi = (base_octave + 1) * 12 + interval + octave_offset
                name = midi_to_name[midi % 12]
                octave = midi // 12 - 1
                dur = 0.0625 if density == 'dense' else 0.125
                notes.append(mp.note(name, octave, duration=dur))

        return notes

    def _make_block_chord(self, root, intervals, base_octave, voicing, density):
        """Block chords with octave bass."""
        notes = []
        # Bass note (octave below)
        bass_midi = (base_octave) * 12 + (intervals[0] % 12)
        bass_name = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'][bass_midi % 12]
        bass_octave = bass_midi // 12 - 1
        notes.append(mp.note(bass_name, bass_octave, duration=0.5))

        # Chord tones
        chord_notes = _make_notes(root, intervals, base_octave)
        notes.extend(chord_notes)

        # Add octave doubling for dense
        if density == 'dense':
            for cn in chord_notes:
                notes.append(mp.note(cn.name, cn.num + 1, duration=0.5))

        return notes

    def _make_broken_chord(self, root, intervals, base_octave, density):
        """Alberti bass style: root-5th-3rd-5th pattern, extended for complex chords."""
        if len(intervals) < 3:
            intervals = [0, 4, 7]  # Force major triad

        notes = []
        repeats = {'sparse': 2, 'medium': 4, 'dense': 8}.get(density, 4)

        # For extended chords (4+ tones), use ascending broken chord
        # For triads, use classic Alberti bass pattern
        if len(intervals) >= 4:
            # Ascending broken chord: root - 3rd - 5th - 7th - 9th - 13th...
            pattern = list(range(len(intervals)))
        else:
            # Classic Alberti: root - 5th - 3rd - 5th
            pattern = [0, 2, 1, 2]

        pattern_len = len(pattern)
        # Round up: ensure at least one full cycle
        num_cycles = (repeats + pattern_len - 1) // pattern_len
        if num_cycles == 0:
            num_cycles = 1
        for _ in range(num_cycles):
            for idx in pattern:
                interval = intervals[idx]
                midi = (base_octave + 1) * 12 + interval
                name = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'][midi % 12]
                octave = midi // 12 - 1
                notes.append(mp.note(name, octave, duration=0.125))

        return notes
