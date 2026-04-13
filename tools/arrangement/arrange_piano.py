"""
Piano arrangement tool.

Combines melody extraction, harmony analysis, and accompaniment generation
into a single piano arrangement: right hand (melody) + left hand (accompaniment).
"""

import musicpy as mp

from tools.analysis.extract_melody import ExtractMelodyTool
from tools.analysis.analyze_harmony import AnalyzeHarmonyTool
from tools.harmony.generate_accompaniment import GenerateAccompanimentTool


VALID_STYLES = {'classical', 'romantic', 'pop'}

# Piano range: A0 = MIDI 21, C8 = MIDI 108
PIANO_LOW = 21
PIANO_HIGH = 108


def _clamp_to_piano_range(notes: list) -> list:
    """Remove or shift notes outside piano range."""
    result = []
    for note in notes:
        if hasattr(note, 'degree'):
            if note.degree < PIANO_LOW:
                # Shift up one or more octaves
                while note.degree < PIANO_LOW:
                    note.num += 1
            elif note.degree > PIANO_HIGH:
                # Shift down
                while note.degree > PIANO_HIGH:
                    note.num -= 1
        result.append(note)
    return result


class ArrangePianoTool:
    """Arrange any piece for piano solo (right hand melody + left hand accompaniment)."""

    name = "arrange_for_piano"
    description = (
        "Arrange a piece for piano solo. Extracts the melody for the right hand "
        "and generates accompaniment for the left hand. "
        "Styles: classical (Alberti bass), romantic (wide arpeggios), pop (block chords). "
        "Output is a 2-track piece within piano range."
    )

    def run(self, piece, style: str = 'classical',
            voicing: str = 'closed', hand_split: str = 'auto') -> mp.P.__class__:
        """
        Arrange a piece for piano.

        Args:
            piece: A musicpy piece object.
            style: 'classical', 'romantic', or 'pop'.
            voicing: 'closed' or 'open'.
            hand_split: 'auto' or a note name like 'C3'.

        Returns:
            A 2-track piece: RH (melody) + LH (accompaniment).
        """
        if style not in VALID_STYLES:
            raise ValueError(
                f"Invalid style '{style}'. Must be one of: {', '.join(sorted(VALID_STYLES))}"
            )

        # Step 1: Extract melody
        melody_tool = ExtractMelodyTool()
        melody = melody_tool.run(piece)

        # Step 2: Analyze harmony
        harmony_tool = AnalyzeHarmonyTool()
        harmony = harmony_tool.run(piece, granularity='measure')

        # Step 3: Generate accompaniment
        pattern_map = {
            'classical': 'broken_chord',
            'romantic': 'arpeggio',
            'pop': 'block_chord',
        }
        accomp_tool = GenerateAccompanimentTool()

        # Calculate total measures from melody span
        # Each measure = 4 beats (4/4 time), so total_measures = melody_beats / 4
        melody_interval = getattr(melody, 'interval', None)
        melody_beats = sum(melody_interval) if melody_interval else 0
        total_measures = max(len(harmony), int(melody_beats / 4.0) + 1)

        accompaniment = accomp_tool.run(
            harmony,
            style=style,
            pattern=pattern_map[style],
            voicing=voicing,
            total_measures=total_measures,
        )

        # Step 4: Clamp to piano range
        melody_notes = list(melody) if hasattr(melody, '__iter__') else []
        melody_intervals = getattr(melody, 'interval', None)
        accomp_notes = list(accompaniment) if hasattr(accompaniment, '__iter__') else []
        accomp_intervals = getattr(accompaniment, 'interval', None)

        melody_notes = _clamp_to_piano_range(melody_notes)
        accomp_notes = _clamp_to_piano_range(accomp_notes)

        # Step 4b: Fill melody gaps — extend notes to reach next note
        if melody_notes and melody_intervals:
            for i in range(len(melody_notes)):
                dur = getattr(melody_notes[i], 'duration', 0.25)
                gap = melody_intervals[i]
                if gap > dur + 0.05:
                    # Extend note to fill gap, add slight sustain overlap
                    melody_notes[i].duration = max(dur, gap - 0.05)

        # Step 4c: Add melody dynamics — phrase structure
        if melody_notes and melody_intervals:
            for i, n in enumerate(melody_notes):
                # Higher notes slightly louder (natural singing quality)
                degree = getattr(n, 'degree', 60)
                base_vol = 85 + min(25, (degree - 60) * 0.5)
                # Every 8 notes: slight crescendo then decrescendo
                phrase_pos = i % 8
                if phrase_pos < 4:
                    vol_mod = 0.9 + 0.1 * (phrase_pos / 4)  # Build up
                else:
                    vol_mod = 1.0 - 0.1 * ((phrase_pos - 4) / 4)  # Release
                n.volume = max(70, min(127, int(base_vol * vol_mod)))

        # Step 5: Build 2-track piano piece
        rh_track = (mp.chord(melody_notes, interval=melody_intervals)
                    if melody_notes else mp.chord([]))
        lh_track = (mp.chord(accomp_notes, interval=accomp_intervals)
                    if accomp_notes else mp.chord([]))

        result = mp.P(
            tracks=[rh_track, lh_track],
            instruments=[1, 1],  # Both piano
            start_times=[0, 0],
            bpm=piece.bpm if piece.bpm else 120,
        )
        return result
