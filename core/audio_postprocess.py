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


def estimate_tempo(piece: mp.P, default_bpm: int = 120) -> float:
    """Estimate the tempo (BPM) of a MIDI piece from note onset intervals.

    Analyzes the time intervals between notes across all tracks to find the
    most common beat subdivision, then converts it to beats per minute.

    Args:
        piece: The MIDI piece to analyze.
        default_bpm: Fallback BPM if estimation fails.

    Returns:
        Estimated tempo in BPM, clamped to [40, 240].
    """
    if not piece.tracks:
        return default_bpm

    onset_times = []
    for track in piece.tracks:
        track_time = 0.0
        notes = track.notes if hasattr(track, 'notes') else list(track)
        for i, note in enumerate(notes):
            onset_times.append(track_time)
            intervals = getattr(track, 'interval', [])
            if i < len(intervals):
                track_time += intervals[i]

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
    return max(40.0, min(240.0, round(bpm, 1)))


def quantize_rhythm(piece: mp.P, subdivision: float = 0.25) -> mp.P:
    """Quantize note timings to the nearest beat subdivision.

    Snaps each note's onset time to a grid defined by the subdivision
    value (e.g., 0.25 for sixteenth-note grid).

    Args:
        piece: The MIDI piece to quantize.
        subdivision: The time grid size in beats (default: 0.25).

    Returns:
        A new piece with quantized note timings.
    """
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


def normalize_velocities(piece: mp.P, min_vel: int = 40, max_vel: int = 110) -> mp.P:
    """Normalize note velocities to a specified range.

    Performs linear rescaling of all note volumes across the entire piece
    so that the quietest note maps to `min_vel` and the loudest to `max_vel`.

    Args:
        piece: The MIDI piece to normalize.
        min_vel: Minimum velocity after normalization.
        max_vel: Maximum velocity after normalization.

    Returns:
        A new piece with normalized velocities.
    """
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


def remove_duplicate_notes(piece: mp.P, threshold: float = 0.1) -> mp.P:
    """Remove duplicate notes that occur at approximately the same time with the same pitch.

    When two notes share the same pitch and their onsets are within `threshold`
    beats of each other, the louder note is kept and the softer one is removed.

    Args:
        piece: The MIDI piece to clean.
        threshold: Maximum time difference (in beats) to consider notes as duplicates.

    Returns:
        A new piece with duplicate notes removed.
    """
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
            replacement = None
            for j, (prev_time, prev_note) in enumerate(zip(kept_times, kept)):
                time_diff = abs(current_time - prev_time)
                pitch_same = (getattr(note, 'degree', 0) == getattr(prev_note, 'degree', 0))
                if time_diff < threshold and pitch_same:
                    is_dup = True
                    if getattr(note, 'volume', 60) > getattr(prev_note, 'volume', 60):
                        replacement = (j, note, current_time)
                    break

            if replacement:
                idx, new_note, new_time = replacement
                kept.pop(idx)
                kept_times.pop(idx)
                kept.append(new_note)
                kept_times.append(new_time)
            elif not is_dup:
                kept.append(note)
                kept_times.append(current_time)

            if i < len(intervals):
                current_time += intervals[i]

        if len(kept) < len(notes):
            if len(kept) > 1:
                actual_intervals = [0.0] + [kept_times[i] - kept_times[i-1] for i in range(1, len(kept_times))]
            else:
                actual_intervals = [0.0]
            new_track = mp.chord(kept, interval=actual_intervals)
            result.tracks[track_idx] = new_track

    return result


def cleanup_durations(piece: mp.P) -> mp.P:
    """Snap note durations to standard musical values.

    Rounds each note's duration to the nearest standard musical value
    (1/64, 1/32, 1/16, 1/8, 1/4, 1/2, whole note).

    Args:
        piece: The MIDI piece to clean.

    Returns:
        A new piece with snapped note durations.
    """
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


def postprocess_midi(piece: mp.P, subdivision: float = 0.25,
                     min_vel: int = 40, max_vel: int = 110) -> mp.P:
    """Apply the full postprocessing pipeline to a MIDI piece.

    Runs quantization, duration cleanup, duplicate removal, and velocity
    normalization in sequence.

    Args:
        piece: The raw MIDI piece to process.
        subdivision: Quantization grid size in beats (default: 0.25).
        min_vel: Minimum velocity for normalization.
        max_vel: Maximum velocity for normalization.

    Returns:
        The fully postprocessed MIDI piece.
    """
    result = quantize_rhythm(piece, subdivision=subdivision)
    result = cleanup_durations(result)
    result = remove_duplicate_notes(result)
    result = normalize_velocities(result, min_vel=min_vel, max_vel=max_vel)
    return result


def _flatten_piece(piece: mp.P) -> mp.chord:
    """Flatten all tracks of a piece into a single chord."""
    all_notes = []
    all_intervals = []
    for track in piece.tracks:
        notes = track.notes if hasattr(track, 'notes') else list(track)
        all_notes.extend(notes)
        ivs = getattr(track, 'interval', [])
        all_intervals.extend(ivs)
    return mp.chord(all_notes, interval=all_intervals)


def _parse_scale_string(scale_str: str) -> mp.scale | None:
    """Parse detect_scale output string into a musicpy scale object.

    detect_scale returns 'most likely scales: A major, C# minor, ...'
    We parse the first (most likely) scale and create a scale object.
    """
    try:
        if ':' in scale_str:
            first_scale = scale_str.split(':')[-1].strip().split(',')[0].strip()
        else:
            first_scale = scale_str.strip()

        # Parse "A major" or "F# minor" etc.
        parts = first_scale.split()
        if len(parts) < 2:
            return None
        root_note = parts[0]  # e.g., 'A', 'F#', 'Db'
        mode = parts[1]       # e.g., 'major', 'minor', 'dorian'

        # Map mode names to musicpy internal names
        mode_map = {
            'major': 'major',
            'minor': 'minor',
            'dorian': 'dorian',
            'phrygian': 'phrygian',
            'lydian': 'lydian',
            'mixolydian': 'mixolydian',
            'locrian': 'locrian',
        }
        mode = mode_map.get(mode, mode)

        # Create scale object
        return mp.scale(start=mp.note(root_note, 4), mode=mode)
    except Exception:
        return None


def estimate_tempo_enhanced(piece: mp.P, default_bpm: int = 65) -> float:
    """Estimate tempo using musicpy's built-in rhythm analysis.

    Falls back to onset-based estimate_tempo if musicpy analysis fails.

    Args:
        piece: The MIDI piece to analyze.
        default_bpm: Fallback BPM if estimation fails.

    Returns:
        Estimated tempo in BPM, clamped to [40, 240].
    """
    try:
        if piece.tracks:
            flat = _flatten_piece(piece)
            if flat.notes:
                rhythm = mp.alg.analyze_rhythm(flat)
                if rhythm and hasattr(rhythm, 'interval'):
                    # Use the most common interval as beat reference
                    ivs = rhythm.interval
                    if ivs:
                        most_common = max(set(ivs), key=ivs.count)
                        if 0.1 < most_common < 4.0:
                            bpm = 60.0 / most_common
                            return max(40.0, min(240.0, round(bpm, 1)))
    except Exception:
        pass
    return estimate_tempo(piece, default_bpm=default_bpm)


def extract_melody_pipeline(piece: mp.P, return_info: bool = False) -> mp.P | tuple[mp.P, dict]:
    """Enhanced melody extraction using musicpy built-in functions.

    Pipeline:
    1. remove_duplicates() — eliminate re-triggered same-pitch notes
    2. pitch_filter('C3', 'C6') — restrict to reasonable melody range
    3. detect_scale() — identify the key/scale
    4. adjust_to_scale() — snap out-of-key notes to the detected scale
    5. split_melody() — extract the main melody line
    6. postprocess_midi() — quantize, cleanup durations, normalize velocity

    Args:
        piece: Raw transcribed MIDI piece (from Basic Pitch or OmniAudio).
        return_info: If True, also return a dict with extracted metadata.

    Returns:
        Cleaned piece with single melody track.
        If return_info=True, returns (piece, info_dict).
    """
    info = {}

    if not piece.tracks:
        if return_info:
            return piece, {'key': 'unknown', 'bpm': piece.bpm or 120}
        return piece

    # Step 1: Remove duplicate notes (Basic Pitch re-triggers same pitch)
    result = remove_duplicate_notes(piece)

    # Step 2: Filter to reasonable melody range (C3=48 to C6=84)
    flat = _flatten_piece(result)
    if flat.notes:
        try:
            # pitch_filter returns (chord, start_time) tuple
            low = mp.note('C', 3)
            high = mp.note('C', 6)
            filtered, _ = flat.pitch_filter(x=low, y=high)
            if filtered.notes:
                flat = filtered
        except Exception:
            # Fallback: manual degree filter
            kept = [n for n in flat if hasattr(n, 'degree') and 48 <= n.degree <= 84]
            flat = mp.chord(kept, interval=getattr(flat, 'interval', [0.0] * len(kept)))

    info['notes_after_pitch_filter'] = len(flat) if flat.notes else 0

    # Step 3: Detect the key/scale
    scale_obj = None
    key_str = 'unknown'
    try:
        key_str = mp.alg.detect_scale(flat)
        info['key'] = key_str
        scale_obj = _parse_scale_string(key_str)
    except Exception:
        info['key'] = 'unknown'

    # Step 4: Adjust notes to detected scale (remove out-of-key noise)
    if scale_obj is not None:
        try:
            flat = mp.alg.adjust_to_scale(flat, scale_obj)
        except Exception:
            pass

    info['notes_after_scale_adjust'] = len(flat) if flat.notes else 0

    # Step 5: Extract melody from remaining polyphonic content
    try:
        melody = mp.alg.split_melody(flat, mode='chord')
        if melody is not None and hasattr(melody, 'notes') and melody.notes:
            flat = melody
            info['notes_after_split_melody'] = len(flat)
    except Exception:
        pass

    # Step 6: Build single-track piece and postprocess
    bpm = estimate_tempo_enhanced(result)
    melody_piece = mp.P(
        tracks=[flat],
        instruments=[1],  # Piano
        start_times=[0],
        bpm=bpm,
    )
    info['bpm'] = bpm

    result = postprocess_midi(melody_piece)

    # Ensure single track
    if len(result.tracks) > 1:
        result.tracks = [result.tracks[0]]
        if hasattr(result, 'instruments'):
            result.instruments = [result.instruments[0]]
        if hasattr(result, 'start_times'):
            result.start_times = [result.start_times[0]]

    if return_info:
        return result, info
    return result
