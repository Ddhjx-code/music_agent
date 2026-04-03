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
        accompaniment = accomp_tool.run(
            harmony,
            style=style,
            pattern=pattern_map[style],
            voicing=voicing,
        )

        # Step 4: Clamp to piano range
        melody_notes = list(melody) if hasattr(melody, '__iter__') else []
        accomp_notes = list(accompaniment) if hasattr(accompaniment, '__iter__') else []

        melody_notes = _clamp_to_piano_range(melody_notes)
        accomp_notes = _clamp_to_piano_range(accomp_notes)

        # Step 5: Build 2-track piano piece
        rh_track = mp.chord(melody_notes) if melody_notes else mp.chord([])
        lh_track = mp.chord(accomp_notes) if accomp_notes else mp.chord([])

        result = mp.P(
            tracks=[rh_track, lh_track],
            instruments=[1, 1],  # Both piano
            start_times=[0, 0],
            bpm=piece.bpm if piece.bpm else 120,
        )
        return result
