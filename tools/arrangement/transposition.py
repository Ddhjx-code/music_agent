"""
Transposition utilities for wind ensemble arrangement.

Handles transposing instruments (Bb, Eb) — converting between
concert pitch and written pitch notation.
"""

import musicpy as mp

# Transposing offsets: semitones to ADD to concert pitch to get written pitch.
# Bb instruments (clarinet, trumpet): sound a whole step lower than written.
#   Written = Concert + 2
# Eb instruments (alto sax): sound a major 6th lower than written.
#   Written = Concert + 9
TRANSPOSING_OFFSETS = {
    'clarinet_bb': 2,
    'trumpet_bb': 2,
    'alto_sax_eb': 9,
    'tenor_sax_eb': 14,  # sounds major 9th lower
    'baritone_sax_eb': 21,  # sounds octave + major 6th lower
    'french_horn_f': 7,  # F horn sounds P5 lower
}

# Standard wind ensemble instrumentation
STANDARD_WINDS = [
    'flute',
    'clarinet_bb',
    'alto_sax_eb',
    'trumpet_bb',
    'french_horn',
    'trombone',
    'tuba',
]

# GM program mapping for wind instruments
WIND_PROGRAMS = {
    'flute': 74,        # Flute
    'clarinet_bb': 71,  # Clarinet
    'alto_sax_eb': 65,  # Alto Sax
    'tenor_sax_eb': 66, # Tenor Sax
    'baritone_sax_eb': 65, # Baritone Sax (same GM as alto)
    'trumpet_bb': 56,   # Trumpet
    'french_horn': 60,  # French Horn
    'trombone': 57,     # Trombone
    'tuba': 53,         # Tuba
}


def get_wind_programs(instrumentation: str = 'standard') -> list[int]:
    """Return GM program numbers for the given instrumentation."""
    instruments = _get_instruments(instrumentation)
    return [WIND_PROGRAMS.get(inst, 0) for inst in instruments]


def transpose_note(note, semitones: int) -> mp.note:
    """Transpose a single note by the given number of semitones."""
    n = mp.note(note.name, note.num, duration=getattr(note, 'duration', 0.25))
    if hasattr(note, 'volume'):
        n.volume = note.volume
    # musicpy note arithmetic: note.degree = absolute MIDI number
    new_degree = note.degree + semitones
    # Recompute name and octave
    names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    n.num = new_degree // 12 - 1  # octave
    n.name = names[new_degree % 12]  # pitch class
    return n


def transpose_to_written(notes: list, instrument: str) -> list[mp.note]:
    """Transpose notes from concert pitch to written pitch for a transposing instrument."""
    offset = TRANSPOSING_OFFSETS.get(instrument, 0)
    if offset == 0:
        return list(notes)  # Non-transposing (flute, trombone, tuba, horn)
    return [transpose_note(n, offset) for n in notes]


def transpose_to_concert(notes: list, instrument: str) -> list[mp.note]:
    """Transpose notes from written pitch back to concert pitch."""
    offset = TRANSPOSING_OFFSETS.get(instrument, 0)
    if offset == 0:
        return list(notes)
    return [transpose_note(n, -offset) for n in notes]


def is_transposing(instrument: str) -> bool:
    """Check if an instrument is a transposing instrument."""
    return instrument in TRANSPOSING_OFFSETS and TRANSPOSING_OFFSETS[instrument] != 0


def _get_instruments(instrumentation: str) -> list[str]:
    """Return the list of instruments for a given instrumentation preset."""
    if instrumentation == 'quintet':
        return ['flute', 'clarinet_bb', 'trumpet_bb', 'french_horn', 'trombone']
    return list(STANDARD_WINDS)  # standard
