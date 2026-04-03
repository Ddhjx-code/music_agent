"""
MIDI I/O wrapper around musicpy.

Provides load/save with error handling and track info extraction.
"""

import os

import musicpy as mp


def load_midi(path: str):
    """
    Load a MIDI file and return a musicpy piece.

    Args:
        path: Path to the MIDI file.

    Returns:
        A musicpy piece object.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is empty or not a valid MIDI file.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"MIDI file not found: {path}")

    if os.path.getsize(path) == 0:
        raise ValueError(f"MIDI file is empty: {path}")

    return mp.read(path)


def save_midi(piece, path: str) -> str:
    """
    Save a musicpy piece to a MIDI file.

    Creates parent directories if they don't exist.

    Args:
        piece: A musicpy piece object.
        path: Output MIDI file path.

    Returns:
        The path to the saved file.
    """
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    mp.write(piece, name=path)
    return path


def get_track_info(piece) -> list[dict]:
    """
    Extract summary info for each track in a piece.

    Args:
        piece: A musicpy piece object.

    Returns:
        List of dicts with keys: note_count, instrument.
    """
    info = []
    for i, track_content in enumerate(piece.tracks):
        note_count = len(track_content) if hasattr(track_content, '__len__') else 0
        instrument = piece.instruments[i] if i < len(piece.instruments) else 0
        info.append({
            'note_count': note_count,
            'instrument': instrument,
        })
    return info
