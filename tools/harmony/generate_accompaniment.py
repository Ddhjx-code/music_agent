"""
Accompaniment generation tool.

Generates piano accompaniment patterns from a chord progression
in multiple styles: classical (Alberti bass), romantic (arpeggios), pop (block chords).
"""

import re

import musicpy as mp


# Map chord names to note components
# Handles: Cmajor, Cminor, Cmaj7, C7, Cdim, Caug, Csus2, Csus4, etc.
def _parse_chord_name(chord_str: str) -> tuple[str, list[str]]:
    """
    Parse a chord name like 'Cmajor', 'Am', 'G7' into (root, intervals).

    Returns (root_note, chord_intervals) where intervals are note offsets
    from the root in semitones.
    """
    chord_str = chord_str.strip()

    # Extract root (A-G, possibly with # or b)
    match = re.match(r'^([A-G][#b]?)(.*)', chord_str)
    if not match:
        return 'C', [0, 4, 7]  # Default to C major

    root = match.group(1)
    quality = match.group(2).lower()

    # Determine chord type from quality
    if quality in ('major', 'maj', ''):
        intervals = [0, 4, 7]
    elif quality in ('minor', 'min', 'm'):
        intervals = [0, 3, 7]
    elif quality in ('maj7', 'major7'):
        intervals = [0, 4, 7, 11]
    elif quality in ('7', 'dom7', 'dominant7'):
        intervals = [0, 4, 7, 10]
    elif quality in ('min7', 'm7', 'minor7'):
        intervals = [0, 3, 7, 10]
    elif quality in ('dim', 'diminished'):
        intervals = [0, 3, 6]
    elif quality in ('aug', 'augmented'):
        intervals = [0, 4, 8]
    elif quality in ('sus2',):
        intervals = [0, 2, 7]
    elif quality in ('sus4',):
        intervals = [0, 5, 7]
    elif quality.startswith('maj') and 'omit' in quality:
        intervals = [0, 4, 7, 11]
    elif quality.startswith('m') and '7' in quality:
        intervals = [0, 3, 7, 10]
    elif 'sus4' in quality:
        intervals = [0, 5, 7]
    elif 'sus2' in quality:
        intervals = [0, 2, 7]
    elif 'dim' in quality:
        intervals = [0, 3, 6]
    elif 'aug' in quality:
        intervals = [0, 4, 8]
    elif '7' in quality:
        intervals = [0, 4, 7, 10]
    else:
        intervals = [0, 4, 7]  # Default major

    return root, intervals


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
        """Alberti bass style: root-5th-3rd-5th pattern."""
        if len(intervals) < 3:
            intervals = [0, 4, 7]  # Force major triad

        # Alberti pattern: root - 5th - 3rd - 5th
        alberti_order = [0, 2, 1, 2]  # indices into intervals
        notes = []
        repeats = {'sparse': 2, 'medium': 4, 'dense': 8}.get(density, 4)

        for _ in range(repeats // len(alberti_order)):
            for idx in alberti_order:
                interval = intervals[idx % len(intervals)]
                midi = (base_octave + 1) * 12 + interval
                name = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'][midi % 12]
                octave = midi // 12 - 1
                notes.append(mp.note(name, octave, duration=0.125))

        return notes
