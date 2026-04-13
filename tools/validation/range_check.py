"""
Range validation tool.

Checks that all notes in a piece are within the playable range
of the target instrument.
"""

import musicpy as mp


# Instrument ranges as (low_midi, high_midi)
INSTRUMENT_RANGES = {
    # Piano
    'piano': (21, 108),     # A0 - C8
    # Strings
    'violin': (67, 115),    # G3 - A7
    'viola': (48, 93),      # C3 - E6
    'cello': (36, 88),      # C2 - A5
    'double_bass': (28, 72), # E1 - C5 (sounds octave lower)
    # Woodwinds
    'flute': (72, 108),     # C4 - C8
    'clarinet': (50, 104),  # D3 - G7 (Bb, concert pitch range)
    # Brass
    'trumpet': (60, 95),    # C4 - B6 (Bb)
    'french_horn': (40, 85), # E2 - F5 (double horn)
    'trombone': (40, 77),   # E2 - Bb4
    'tuba': (24, 52),       # Bb0 - F3
    # Saxophones
    'alto_sax': (57, 92),   # D3 - A5 (Eb)
    'tenor_sax': (50, 85),  # Bb2 - F5 (Eb)
    'baritone_sax': (36, 75), # C2 - D5 (Eb)
}


class RangeCheckTool:
    """Validate that notes are within instrument range."""

    name = "validate_range"
    description = (
        "Check that all notes in a piece are within the playable range "
        "of the target instrument. Returns {passed: bool, issues: list}."
    )

    def run(self, piece, instrument: str = 'piano') -> dict:
        """
        Validate instrument range.

        Args:
            piece: A musicpy piece object.
            instrument: Instrument name for range checking.

        Returns:
            Dict with 'passed' (bool) and 'issues' (list of issue dicts).
        """
        low, high = INSTRUMENT_RANGES.get(instrument, (21, 108))
        issues = []

        for track_idx, track_content in enumerate(piece.tracks):
            notes = track_content.notes if hasattr(track_content, 'notes') else list(track_content)
            for note in notes:
                if hasattr(note, 'degree'):
                    if note.degree < low or note.degree > high:
                        issues.append({
                            'type': 'out_of_range',
                            'track': track_idx,
                            'note': str(note),
                            'midi': note.degree,
                            'range': f"{_midi_to_name(low)}-{_midi_to_name(high)}",
                        })

        return {
            'passed': len(issues) == 0,
            'issues': issues,
        }


def _midi_to_name(midi: int) -> str:
    """Convert MIDI note number to note name."""
    names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    note = names[midi % 12]
    octave = (midi // 12) - 1
    return f"{note}{octave}"
