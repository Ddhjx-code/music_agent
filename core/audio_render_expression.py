"""
Audio render expression module.

Pre-processing for MIDI before rendering:
- Velocity mapping by voice role
- Phrase-based expression (crescendo/decrescendo)
- Rubato timing variation
"""

import random

import musicpy as mp

from tools.analysis.voice_detection import detect_voice_roles

VELOCITY_RANGES = {
    'melody': (70, 110),
    'accompaniment': (40, 70),
    'bass': (60, 90),
}


def apply_velocity_mapping(piece: mp.P, profile: str = 'piano') -> mp.P:
    """
    Map note velocities by voice role.

    Analyzes voice roles and applies appropriate velocity ranges:
    - Melody: 70-110 (expressive)
    - Accompaniment: 40-70 (subtle)
    - Bass: 60-90 (solid)

    Args:
        piece: A musicpy piece object.
        profile: Instrument profile ('piano', 'strings', 'winds').

    Returns:
        Copy of piece with mapped velocities.
    """
    if not piece.tracks:
        return piece

    result = piece.copy()
    roles = detect_voice_roles(result)
    melody_indices = set(roles.get('melody', []))
    bass_indices = set(roles.get('bass', []))

    for track_idx, track in enumerate(result.tracks):
        notes = track.notes if hasattr(track, 'notes') else list(track)

        if track_idx in melody_indices:
            min_vel, max_vel = VELOCITY_RANGES['melody']
        elif track_idx in bass_indices:
            min_vel, max_vel = VELOCITY_RANGES['bass']
        else:
            min_vel, max_vel = VELOCITY_RANGES['accompaniment']

        if profile == 'romantic':
            max_vel = min(127, max_vel + 10)

        for note in notes:
            if hasattr(note, 'volume'):
                note.volume = max(min_vel, min(max_vel, note.volume))

    return result


def apply_phrase_expression(piece: mp.P, phrase_length: int = 4,
                           intensity: float = 0.1) -> mp.P:
    """
    Add phrase-based expression: crescendo/decrescendo.

    Within each phrase, notes gradually increase then decrease in velocity.

    Args:
        piece: A musicpy piece object.
        phrase_length: Number of notes per phrase.
        intensity: Strength of expression (0.0-1.0).

    Returns:
        Copy of piece with phrase expression.
    """
    if not piece.tracks:
        return piece

    result = piece.copy()
    for track in result.tracks:
        notes = track.notes if hasattr(track, 'notes') else list(track)
        if not notes:
            continue

        for phrase_start in range(0, len(notes), phrase_length):
            phrase_notes = notes[phrase_start:phrase_start + phrase_length]
            count = len(phrase_notes)
            if count < 2:
                continue

            for i, note in enumerate(phrase_notes):
                if not hasattr(note, 'volume'):
                    continue
                mid = count / 2
                if i < mid:
                    delta = int(intensity * 127 * (i / mid))
                else:
                    delta = int(intensity * 127 * ((count - 1 - i) / (count - mid)))
                note.volume = max(1, min(127, note.volume + delta))

    return result


def apply_rubato(piece: mp.P, amount: float = 0.01, seed: int | None = None) -> mp.P:
    """
    Apply slight timing variations for human feel.

    Args:
        piece: A musicpy piece object.
        amount: Maximum timing offset in beats (default +/-0.01).
        seed: Random seed for reproducibility.

    Returns:
        Copy of piece with timing variations.
    """
    if not piece.tracks:
        return piece

    if seed is not None:
        random.seed(seed)

    result = piece.copy()
    for track in result.tracks:
        intervals = list(getattr(track, 'interval', []))
        if not intervals:
            continue

        for i in range(1, len(intervals)):
            offset = random.uniform(-amount, amount)
            intervals[i] = max(0.01, intervals[i] + offset)

        track.interval = intervals

    return result


def apply_full_expression(piece: mp.P, profile: str = 'piano',
                          phrase_length: int = 4,
                          rubato_amount: float = 0.01) -> mp.P:
    """
    Run full expression pre-processing pipeline.

    Order: velocity mapping -> phrase expression -> rubato.

    Args:
        piece: A musicpy piece object.
        profile: Instrument profile.
        phrase_length: Notes per phrase.
        rubato_amount: Timing variation amount.

    Returns:
        Processed piece.
    """
    result = apply_velocity_mapping(piece, profile=profile)
    result = apply_phrase_expression(result, phrase_length=phrase_length)
    result = apply_rubato(result, amount=rubato_amount)
    return result
