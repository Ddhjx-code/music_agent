"""
Music Summary JSON generator.

Produces a compact, LLM-friendly summary from a musicpy piece.
This is what the LLM sees — NOT per-note data.
"""

import musicpy as mp


# Piano range: A0 = MIDI 21, C8 = MIDI 108
MIDI_TO_NOTE_NAME = [
    'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'
]


def midi_to_note_name(midi_num: int) -> str:
    """Convert MIDI note number to note name like 'C4'."""
    note = MIDI_TO_NOTE_NAME[midi_num % 12]
    octave = (midi_num // 12) - 1
    return f"{note}{octave}"


def _get_track_midi_range(track_content) -> tuple[int, int] | None:
    """Get min and max MIDI note numbers in a track."""
    notes = []
    for item in track_content:
        if hasattr(item, 'degree'):
            notes.append(item.degree)
    if not notes:
        return None
    return min(notes), max(notes)


def _infer_track_role(track_content, track_index: int) -> str:
    """
    Infer a track's role from its content.

    Heuristics:
    - Channel 10 (track with instrument mapped to drums) → percussion
    - Highest average pitch → melody
    - Lowest average pitch → bass
    - Everything else → harmony
    """
    degrees = [item.degree for item in track_content if hasattr(item, 'degree')]
    if not degrees:
        return 'harmony'

    avg_pitch = sum(degrees) / len(degrees)

    # High range = melody, low range = bass
    if avg_pitch >= 72:  # C5 and above
        return 'melody'
    elif avg_pitch <= 48:  # C3 and below
        return 'bass'
    else:
        return 'harmony'


def _detect_key(piece) -> str:
    """
    Detect the key of the piece using musicpy's algorithm module.

    Falls back to 'C' if detection fails.
    """
    try:
        # Try to detect from the first track's content
        first_track = piece.tracks[0]
        if hasattr(first_track, 'notes'):
            notes_list = first_track.notes
        else:
            notes_list = list(first_track)

        if notes_list:
            result = mp.alg.detect(mp.chord(notes_list))
            if result:
                # Result is like 'Cmaj7' — extract root
                root = result[0]
                # Check if minor
                if 'm' in result[1:]:
                    return f"{root}m"
                return root
    except Exception:
        pass

    return 'C'


def _detect_chord_progression(piece, measures_per_chunk: int = 1) -> list[dict]:
    """
    Detect chord progression per measure (or per chunk).

    Returns list of {measure, chord} dicts.
    """
    progression = []
    measure_num = 1

    for track in piece.tracks:
        if not hasattr(track, 'notes') and not hasattr(track, '__iter__'):
            continue

        notes = track.notes if hasattr(track, 'notes') else list(track)
        if not notes:
            continue

        # Group notes by measure (using duration to estimate position)
        current_pos = 0.0
        current_notes = []

        for note in notes:
            duration = getattr(note, 'duration', 0.25)
            current_notes.append(note)
            current_pos += duration

            if current_pos >= measures_per_chunk:
                # Detect chord for this chunk
                if current_notes:
                    try:
                        chord_obj = mp.chord(current_notes)
                        chord_name = mp.alg.detect(chord_obj)
                        if chord_name:
                            progression.append({
                                'measure': measure_num,
                                'chord': chord_name,
                            })
                    except Exception:
                        progression.append({
                            'measure': measure_num,
                            'chord': 'unknown',
                        })
                measure_num += 1
                current_notes = []
                current_pos = 0.0

        # Handle remaining notes
        if current_notes:
            try:
                chord_obj = mp.chord(current_notes)
                chord_name = mp.alg.detect(chord_obj)
                progression.append({
                    'measure': measure_num,
                    'chord': chord_name if chord_name else 'unknown',
                })
            except Exception:
                progression.append({
                    'measure': measure_num,
                    'chord': 'unknown',
                })

        break  # Only analyze first track for chord progression

    return progression


def _detect_form(num_measures: int) -> list[dict]:
    """
    Simple form detection: split into A/B sections.

    For Phase 1, just split in half.
    """
    if num_measures <= 4:
        return [{'section': 'A', 'measures': f"1-{num_measures}"}]

    half = num_measures // 2
    return [
        {'section': 'A', 'measures': f"1-{half}"},
        {'section': 'B', 'measures': f"{half + 1}-{num_measures}"},
    ]


def _estimate_measures(piece) -> int:
    """Estimate number of measures from track durations."""
    max_duration = 0
    for track in piece.tracks:
        if hasattr(track, 'notes'):
            total = sum(getattr(n, 'duration', 0.25) for n in track.notes)
        else:
            total = sum(getattr(n, 'duration', 0.25) for n in track)
        max_duration = max(max_duration, total)

    # Assume 4/4: 1 measure = 1.0 (quarter note = 0.25, 4 per measure)
    return max(1, int(max_duration))


def generate_summary(piece, title: str = "Untitled") -> dict:
    """
    Generate a compact, LLM-friendly summary from a musicpy piece.

    Args:
        piece: A musicpy piece object.
        title: Title for the summary.

    Returns:
        Dict matching the MUSIC_SUMMARY_SCHEMA from plan.md.
    """
    num_measures = _estimate_measures(piece)
    key = _detect_key(piece)
    chord_progression = _detect_chord_progression(piece)
    form = _detect_form(num_measures)

    tracks_info = []
    for i, track_content in enumerate(piece.tracks):
        notes = track_content.notes if hasattr(track_content, 'notes') else list(track_content)
        degrees = [n.degree for n in notes if hasattr(n, 'degree')]

        midi_range = _get_track_midi_range(track_content)
        pitch_range = f"{midi_to_note_name(midi_range[0])}-{midi_to_note_name(midi_range[1])}" if midi_range else "N/A"

        velocities = [getattr(n, 'volume', 100) for n in notes if hasattr(n, 'volume')]
        avg_velocity = int(sum(velocities) / len(velocities)) if velocities else 100

        instrument = piece.instruments[i] if i < len(piece.instruments) else 0

        tracks_info.append({
            'name': f"Track {i + 1}",
            'instrument': instrument,
            'role': _infer_track_role(track_content, i),
            'pitch_range': pitch_range,
            'avg_velocity': avg_velocity,
        })

    return {
        'title': title,
        'key': key,
        'bpm': int(piece.bpm) if piece.bpm else 120,
        'time_signature': '4/4',
        'num_measures': num_measures,
        'num_tracks': len(piece.tracks),
        'tracks': tracks_info,
        'chord_progression': chord_progression,
        'form': form,
    }
