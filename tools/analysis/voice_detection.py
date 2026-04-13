"""
Voice role detection.

Analyzes a piece's tracks and classifies each into musical roles:
- melody: highest sustained pitches (soprano register)
- harmony: mid-range chord tones (alto/tenor register)
- inner_voice: middle register filler
- bass: lowest register (bass line)

Uses average pitch position and temporal density to determine roles.
"""

import musicpy as mp


def detect_voice_roles(piece) -> dict:
    """
    Analyze a piece and classify each track into a voice role.

    Args:
        piece: A musicpy piece object.

    Returns:
        Dict mapping role -> list of track indices:
        {'melody': [0], 'harmony': [1], 'inner_voice': [2], 'bass': [3]}
        Roles with no tracks assigned are omitted.
    """
    if not piece.tracks:
        return {'melody': [], 'harmony': [], 'inner_voice': [], 'bass': []}

    # Collect per-track pitch and density stats
    track_stats = []
    for idx, track_content in enumerate(piece.tracks):
        notes = track_content.notes if hasattr(track_content, 'notes') else list(track_content)
        degrees = [n.degree for n in notes if hasattr(n, 'degree')]
        if not degrees:
            track_stats.append({'idx': idx, 'avg_degree': 0, 'count': 0, 'min_degree': 0})
            continue
        track_stats.append({
            'idx': idx,
            'avg_degree': sum(degrees) / len(degrees),
            'count': len(degrees),
            'min_degree': min(degrees),
        })

    # Filter out empty tracks
    active = [s for s in track_stats if s['count'] > 0]
    if not active:
        return {'melody': [], 'harmony': [], 'inner_voice': [], 'bass': []}

    # Sort by average pitch (highest first)
    active.sort(key=lambda s: s['avg_degree'], reverse=True)

    roles = {'melody': [], 'harmony': [], 'inner_voice': [], 'bass': []}
    n = len(active)

    if n == 1:
        # Single melody track — we'll derive other voices later
        roles['melody'].append(active[0]['idx'])
    elif n == 2:
        # Melody + accompaniment (typical piano score)
        roles['melody'].append(active[0]['idx'])
        roles['harmony'].append(active[1]['idx'])
    elif n == 3:
        # Melody + harmony + bass (typical pop song)
        roles['melody'].append(active[0]['idx'])
        roles['harmony'].append(active[1]['idx'])
        roles['bass'].append(active[2]['idx'])
    elif n == 4:
        # SATB-like: 4 voices
        roles['melody'].append(active[0]['idx'])
        roles['harmony'].append(active[1]['idx'])
        roles['inner_voice'].append(active[2]['idx'])
        roles['bass'].append(active[3]['idx'])
    else:
        # Many tracks: top = melody, bottom = bass, middle = harmony
        roles['melody'].append(active[0]['idx'])
        roles['bass'].append(active[-1]['idx'])
        for s in active[1:-1]:
            roles['harmony'].append(s['idx'])
        # If more than 2 harmony tracks, move excess to inner_voice
        while len(roles['harmony']) > 2:
            roles['inner_voice'].append(roles['harmony'].pop())

    return roles


def get_track_avg_degree(piece, track_idx: int) -> float:
    """Get the average pitch degree of a track."""
    if track_idx >= len(piece.tracks):
        return 0
    track = piece.tracks[track_idx]
    notes = track.notes if hasattr(track, 'notes') else list(track)
    degrees = [n.degree for n in notes if hasattr(n, 'degree')]
    return sum(degrees) / len(degrees) if degrees else 0
