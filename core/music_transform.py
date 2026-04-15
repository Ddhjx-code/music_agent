"""
music_transform.py — bidirectional conversion between musicpy pieces and structured JSON.

This is the bridge that lets the LLM deeply participate in music editing:
- piece_to_json: full musicpy piece → LLM-readable JSON (summary + per-note data)
- json_to_piece: LLM-modified JSON → musicpy piece (for further processing)
"""

import re

import musicpy as mp

from core.json_schema import generate_summary


def piece_to_json(piece, include_notes: bool = True) -> dict:
    """
    Convert a musicpy piece to structured JSON.

    Args:
        piece: A musicpy piece object.
        include_notes: If True, include per-note data (pitch, duration, velocity, start_time).

    Returns:
        Dict with 'summary' and 'tracks' sections.
    """
    summary = generate_summary(piece)

    tracks_data = []
    for track_idx, track_content in enumerate(piece.tracks):
        notes = track_content.notes if hasattr(track_content, 'notes') else list(track_content)
        intervals = getattr(track_content, 'interval', None)
        instrument = piece.instruments[track_idx] if track_idx < len(piece.instruments) else 0

        track_info = {
            'index': track_idx,
            'instrument': instrument,
            'note_count': len(notes),
        }

        if include_notes:
            track_info['notes'] = _notes_to_json(notes, intervals)

        tracks_data.append(track_info)

    return {
        'summary': summary,
        'tracks': tracks_data,
    }


def _notes_to_json(notes, intervals=None) -> list[dict]:
    """Convert note list to JSON-serializable format with start times."""
    result = []
    current_time = 0.0
    for i, note in enumerate(notes):
        iv = intervals[i] if intervals and i < len(intervals) else 0
        if i > 0:
            current_time += iv
        note_data = {
            'pitch': getattr(note, 'degree', 60),
            'name': _degree_to_note_name(getattr(note, 'degree', 60)),
            'duration': getattr(note, 'duration', 0.25),
            'velocity': getattr(note, 'volume', 100),
            'start_time': round(current_time, 4),
        }
        result.append(note_data)
    return result


def _degree_to_note_name(degree: int) -> str:
    """Convert MIDI note number to note name like 'C4'."""
    names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    note = names[degree % 12]
    octave = (degree // 12) - 1
    return f"{note}{octave}"


def json_to_piece(data: dict) -> mp.P.__class__:
    """
    Convert structured JSON back to a musicpy piece.

    Args:
        data: Dict with 'summary' and 'tracks' sections (from piece_to_json).

    Returns:
        A musicpy piece object.
    """
    tracks = []
    instruments = []
    start_times = []
    bpm = data['summary'].get('bpm', 120)

    for track_data in data['tracks']:
        notes = []
        intervals = []
        prev_time = 0.0

        for note_data in track_data['notes']:
            pitch = note_data['pitch']
            name = _degree_to_note_name(pitch)
            match = re.match(r'([A-G][#b]?)(\d+)', name)
            if match:
                note_name = match.group(1)
                note_octave = int(match.group(2))
                n = mp.note(note_name, note_octave,
                            duration=note_data['duration'],
                            volume=note_data['velocity'])
            else:
                n = mp.note('C', 4, duration=note_data['duration'],
                            volume=note_data['velocity'])

            notes.append(n)
            start_time = note_data['start_time']
            if intervals:
                intervals.append(start_time - prev_time)
            else:
                intervals.append(0.0)
            prev_time = start_time

        chord_obj = mp.chord(notes, interval=intervals)
        tracks.append(chord_obj)
        instruments.append(track_data.get('instrument', 1))
        start_times.append(0)

    return mp.P(
        tracks=tracks,
        instruments=instruments,
        start_times=start_times,
        bpm=bpm,
    )
