"""
Accompaniment generation tool using musicpy.

Generates piano accompaniment patterns from a chord progression
using musicpy's chord and rhythm APIs.
"""

import re
import musicpy as mp


def _parse_quality(quality: str) -> list[int]:
    """Parse chord quality string into semitone intervals."""
    quality = quality.lower().strip()

    if quality in ('major', 'maj', ''):
        return [0, 4, 7]
    if quality == 'm':
        return [0, 3, 7]
    if quality.startswith('min') or quality.startswith('minor'):
        if '13' in quality:
            return [0, 3, 7, 10, 14, 21]
        if '11' in quality:
            return [0, 3, 7, 10, 17]
        if '9' in quality:
            return [0, 3, 7, 10, 14]
        if '7' in quality:
            return [0, 3, 7, 10]
        return [0, 3, 7]
    if quality.startswith('m'):
        if '13' in quality:
            return [0, 3, 7, 10, 14, 21]
        if '11' in quality:
            return [0, 3, 7, 10, 17]
        if '9' in quality:
            return [0, 3, 7, 10, 14]
        if '7' in quality:
            return [0, 3, 7, 10]
        return [0, 3, 7]
    if quality.startswith('maj'):
        if '13' in quality:
            return [0, 4, 7, 11, 14, 21]
        if '11' in quality:
            return [0, 4, 7, 11, 17]
        if '9' in quality:
            return [0, 4, 7, 11, 14]
        return [0, 4, 7, 11]
    if 'dim' in quality:
        return [0, 3, 6]
    if 'aug' in quality:
        if '7' in quality:
            return [0, 4, 8, 10]
        return [0, 4, 8]
    if '13sus4' in quality:
        return [0, 5, 7, 10, 14, 21]
    if '13sus2' in quality:
        return [0, 2, 7, 10, 14, 21]
    if '7sus4' in quality or '9sus4' in quality or '11sus4' in quality:
        return [0, 5, 7, 10]
    if '7sus2' in quality:
        return [0, 2, 7, 10]
    if 'sus4' in quality:
        return [0, 5, 7]
    if 'sus2' in quality:
        return [0, 2, 7]
    if '13' in quality:
        return [0, 4, 7, 10, 14, 21]
    if '11' in quality:
        return [0, 4, 7, 10, 14, 17]
    if '9' in quality:
        return [0, 4, 7, 10, 14]
    if '7' in quality:
        return [0, 4, 7, 10]
    if quality == '69' or quality == '6add9':
        return [0, 4, 7, 9, 14]
    if quality == '6':
        return [0, 4, 7, 9]
    if quality == 'add9':
        return [0, 4, 7, 14]

    return [0, 4, 7]


class GenerateAccompanimentTool:
    """Generate piano accompaniment from a chord progression using musicpy."""

    name = "generate_accompaniment"
    description = (
        "Generate piano accompaniment from a chord progression. "
        "Supports classical (broken chords), romantic (arpeggios), "
        "and pop (block chords + octave bass) styles."
    )

    def run(self, harmony: list[dict], style: str = 'classical',
            pattern: str = 'broken_chord', voicing: str = 'closed',
            density: str = 'medium', total_measures: int = None) -> mp.chord:
        """
        Generate accompaniment using musicpy.
        """
        if not harmony:
            return mp.chord([])

        if pattern == 'broken_chord' and style == 'romantic':
            pattern = 'arpeggio'
        elif pattern == 'broken_chord' and style == 'pop':
            pattern = 'block_chord'

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
            chord_notes = self._chord_str_to_notes(chord_str)
            if not chord_notes:
                continue

            if pattern == 'arpeggio':
                notes, timings = self._arpeggio(chord_notes, density, voicing)
            elif pattern == 'block_chord':
                notes, timings = self._block_chord(chord_notes, density)
            else:
                notes, timings = self._broken_chord(chord_notes)

            all_notes.extend(notes)
            all_intervals.extend(timings)

        if not all_notes:
            return mp.chord([])
        if not all_intervals:
            all_intervals = [0.0] * len(all_notes)
        return mp.chord(all_notes, interval=all_intervals)

    def _chord_str_to_notes(self, chord_str: str) -> list:
        """Parse chord name string to musicpy notes."""
        try:
            c = mp.chord(chord_str)
            notes = list(c)
            if all(hasattr(n, 'name') and len(getattr(n, 'name', '')) <= 3 for n in notes):
                return notes
        except Exception:
            pass

        match = re.match(r'^(?:note\s+)?([A-G][#b]?)(.*)', chord_str)
        if not match:
            return []

        root = match.group(1)
        quality = match.group(2).lower().strip()
        quality = re.sub(r'/[A-G][#b]?\s*$', '', quality)
        quality = re.sub(r'\s*sort\s+as\s+\[.*?\]', '', quality)
        quality = re.sub(r'\s*omit\s+\w+', '', quality)
        quality = quality.strip()

        intervals = _parse_quality(quality)
        if not intervals:
            return []

        midi_to_name = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        root_idx = midi_to_name.index(root) if root in midi_to_name else 0
        base_octave = 3 if root in 'CDE' else 2

        notes = []
        for interval in intervals:
            midi = (base_octave + 1) * 12 + (root_idx + interval) % 12
            note_name = midi_to_name[midi % 12]
            note_octave = midi // 12 - 1
            notes.append(mp.note(note_name, note_octave, duration=0.25))

        return notes

    def _arpeggio(self, chord_notes, density, voicing):
        """Create arpeggio pattern spanning 2+ octaves."""
        sweeps = {'sparse': 1, 'medium': 2, 'dense': 3}.get(density, 2)
        sweep_dur = 1.0
        notes = []
        timings = []

        for sweep in range(sweeps):
            extended = list(chord_notes)
            if voicing == 'open':
                extended = chord_notes + chord_notes

            for i, n in enumerate(extended):
                vel = 90 if i == 0 else 70
                octave_shift = sweep  # Each sweep goes up an octave
                new_note = mp.note(
                    getattr(n, 'name', 'C'),
                    getattr(n, 'num', 4) + octave_shift,
                    duration=0.25,
                    volume=vel
                )
                notes.append(new_note)
                timings.append(sweep_dur / len(extended))

        return notes, timings

    def _block_chord(self, chord_notes, density):
        """Create block chord with bass octave."""
        notes = []
        timings = []

        bass = mp.note(
            getattr(chord_notes[0], 'name', 'C'),
            getattr(chord_notes[0], 'num', 3) - 1,
            duration=2.0, volume=90
        )
        notes.append(bass)
        timings.append(0.0)

        for cn in chord_notes:
            new_note = mp.note(
                getattr(cn, 'name', 'C'),
                getattr(cn, 'num', 4),
                duration=2.0, volume=80
            )
            notes.append(new_note)
            timings.append(0.0)

        return notes, timings

    def _broken_chord(self, chord_notes):
        """Create broken chord (Alberti bass style)."""
        if len(chord_notes) < 3:
            root = chord_notes[0] if chord_notes else mp.note('C', 4)
            fifth = mp.note('G', getattr(root, 'num', 4) + 1)
            chord_notes = [root, fifth, mp.note('E', getattr(root, 'num', 4))]

        pattern_idx = [0, 2, 1, 2]
        notes = []
        timings = []

        for _ in range(8):
            idx = pattern_idx[len(notes) % len(pattern_idx)]
            cn = chord_notes[idx % len(chord_notes)]
            new_note = mp.note(
                getattr(cn, 'name', 'C'),
                getattr(cn, 'num', 4),
                duration=0.5,
                volume=80 if idx < 2 else 70
            )
            notes.append(new_note)
            timings.append(0.5)

        return notes, timings
