"""
Audio post-processing module.

Functions to clean up and improve transcribed MIDI:
- Rhythm quantization (snap to beat subdivisions)
- Note duration cleanup (normalize to musical values)
- Duplicate/overlap removal
- Velocity normalization (scale to 40-110)
- Tempo estimation from note onsets
"""

from collections import Counter

import musicpy as mp


def estimate_tempo(piece, default_bpm: int = 120) -> float:
    if not piece.tracks:
        return default_bpm

    onset_times = []
    for track in piece.tracks:
        notes = track.notes if hasattr(track, 'notes') else list(track)
        time = 0.0
        for i, note in enumerate(notes):
            onset_times.append(time)
            intervals = getattr(track, 'interval', [])
            if i < len(intervals):
                time += intervals[i]

    if len(onset_times) < 2:
        return default_bpm

    onset_times.sort()
    intervals = [onset_times[i+1] - onset_times[i] for i in range(len(onset_times)-1)]
    valid = [iv for iv in intervals if 0.1 < iv < 4.0]
    if not valid:
        return default_bpm

    rounded = [round(iv * 16) / 16 for iv in valid]
    most_common = Counter(rounded).most_common(1)
    if not most_common:
        return default_bpm

    beat_interval = most_common[0][0]
    if beat_interval <= 0:
        return default_bpm

    bpm = 60.0 / beat_interval
    return max(40, min(240, round(bpm)))


def quantize_rhythm(piece, subdivision: float = 0.25) -> mp.P.__class__:
    if not piece.tracks:
        return piece

    result = piece.copy()
    for track in result.tracks:
        intervals = list(getattr(track, 'interval', []))
        if not intervals:
            continue

        intervals[0] = 0.0
        for i in range(1, len(intervals)):
            intervals[i] = round(intervals[i] / subdivision) * subdivision
            intervals[i] = max(0.0, intervals[i])

        track.interval = intervals

    return result


def normalize_velocities(piece, min_vel: int = 40, max_vel: int = 110) -> mp.P.__class__:
    if not piece.tracks:
        return piece

    result = piece.copy()
    all_velocities = []
    for track in result.tracks:
        notes = track.notes if hasattr(track, 'notes') else list(track)
        for note in notes:
            if hasattr(note, 'volume'):
                all_velocities.append(note.volume)

    if not all_velocities:
        return result

    old_min = min(all_velocities)
    old_max = max(all_velocities)
    old_range = old_max - old_min

    for track in result.tracks:
        notes = track.notes if hasattr(track, 'notes') else list(track)
        for note in notes:
            if hasattr(note, 'volume'):
                if old_range == 0:
                    note.volume = (min_vel + max_vel) // 2
                else:
                    ratio = (note.volume - old_min) / old_range
                    note.volume = max(min_vel, min(max_vel,
                                                   int(min_vel + ratio * (max_vel - min_vel))))

    return result


def remove_duplicate_notes(piece, threshold: float = 0.1) -> mp.P.__class__:
    if not piece.tracks:
        return piece

    result = piece.copy()
    for track_idx, track in enumerate(result.tracks):
        notes = list(track.notes if hasattr(track, 'notes') else list(track))
        if len(notes) < 2:
            continue

        intervals = list(getattr(track, 'interval', []))
        kept = []
        kept_times = []
        current_time = 0.0

        for i, note in enumerate(notes):
            is_dup = False
            for prev_time, prev_note in zip(kept_times, kept):
                time_diff = abs(current_time - prev_time)
                pitch_same = (getattr(note, 'degree', 0) == getattr(prev_note, 'degree', 0))
                if time_diff < threshold and pitch_same:
                    is_dup = True
                    if getattr(note, 'volume', 60) > getattr(prev_note, 'volume', 60):
                        kept.remove(prev_note)
                        kept_times.remove(prev_time)
                        kept.append(note)
                        kept_times.append(current_time)
                    break

            if not is_dup:
                kept.append(note)
                kept_times.append(current_time)

            if i < len(intervals):
                current_time += intervals[i]

        if len(kept) < len(notes):
            new_track = mp.chord(kept, interval=[0.0] + [0.25] * (len(kept) - 1))
            result.tracks[track_idx] = new_track

    return result


def cleanup_durations(piece) -> mp.P.__class__:
    if not piece.tracks:
        return piece

    musical_values = [0.0625, 0.125, 0.25, 0.5, 1.0, 2.0, 4.0]
    result = piece.copy()

    for track in result.tracks:
        notes = track.notes if hasattr(track, 'notes') else list(track)
        for note in notes:
            dur = getattr(note, 'duration', 0.25)
            if dur <= 0:
                continue
            nearest = min(musical_values, key=lambda mv: abs(mv - dur))
            note.duration = nearest

    return result


def postprocess_midi(piece, subdivision: float = 0.25,
                     min_vel: int = 40, max_vel: int = 110) -> mp.P.__class__:
    result = quantize_rhythm(piece, subdivision=subdivision)
    result = cleanup_durations(result)
    result = remove_duplicate_notes(result)
    result = normalize_velocities(result, min_vel=min_vel, max_vel=max_vel)
    return result
