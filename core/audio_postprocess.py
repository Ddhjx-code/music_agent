"""
Audio post-processing module.

Uses musicpy native APIs for music-theoretic operations (scale detection,
melody splitting, standardization) with minimal data-processing glue logic
for handling Basic Pitch transcription artifacts.
"""

from collections import Counter

import musicpy as mp


# ---------------------------------------------------------------------------
# Data-processing glue: merge transcription fragments into sustained notes
# ---------------------------------------------------------------------------

def _sustained_note_merge(piece: mp.P, window: float = 0.3) -> mp.P:
    """Merge fragmented notes from audio transcription into sustained notes.

    Basic Pitch produces many short, same-pitch notes for what should be one
    sustained sung/played note.  This merges consecutive same-degree notes
    whose onset gap is within *window* seconds, keeping the loudest one and
    extending its duration to cover the full span.

    This is **not** a music-theory algorithm — it is data cleanup specific
    to noisy transcription output.

    Args:
        piece: The raw transcribed MIDI piece.
        window: Maximum time gap (in beats) to consider notes as fragments.

    Returns:
        A new piece with merged sustained notes.
    """
    if not piece.tracks:
        return piece

    result = piece.copy()
    new_tracks = []

    for track in result.tracks:
        notes = list(track.notes if hasattr(track, 'notes') else list(track))
        if len(notes) < 2:
            continue

        intervals = list(getattr(track, 'interval', []))

        # Compute absolute onset times
        times = [0.0]
        for i in range(1, len(notes)):
            times.append(times[-1] + intervals[i])

        # Merge: group same-degree notes within window
        merged: list[mp.note] = []
        merged_times: list[float] = []
        merged_ends: list[float] = []

        for time, note in zip(times, notes):
            end_time = time + getattr(note, 'duration', 0.25)
            if merged_times and abs(time - merged_times[-1]) < window and note.degree == merged[-1].degree:
                # Extend the current sustained note
                if end_time > merged_ends[-1]:
                    merged_ends[-1] = end_time
                if getattr(note, 'volume', 60) > getattr(merged[-1], 'volume', 60):
                    merged[-1].volume = note.volume
            else:
                merged.append(mp.note(note.name, note.num,
                                      duration=end_time - time,
                                      volume=getattr(note, 'volume', 60)))
                merged_times.append(time)
                merged_ends.append(end_time)

        # Rebuild intervals from merged onsets
        new_intervals = [0.0]
        for i in range(1, len(merged_times)):
            new_intervals.append(max(0.0, round(merged_times[i] - merged_times[i - 1], 4)))

        # Update note durations to match merged spans
        for i, (note, end_t) in enumerate(zip(merged, merged_ends)):
            note.duration = max(0.01, round(end_t - merged_times[i], 4))

        new_tracks.append(mp.chord(merged, interval=new_intervals))

    result.tracks = new_tracks if new_tracks else result.tracks
    return result


# ---------------------------------------------------------------------------
# Tempo estimation (no musicpy equivalent — keep handwritten)
# ---------------------------------------------------------------------------

def estimate_tempo(piece: mp.P, default_bpm: int = 120) -> float:
    """Estimate the tempo (BPM) from note onset intervals.

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
    intervals = [onset_times[i + 1] - onset_times[i] for i in range(len(onset_times) - 1)]
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


def estimate_tempo_enhanced(piece: mp.P, default_bpm: int = 65) -> float:
    """Estimate tempo using musicpy's rhythm analysis, with fallback.

    Args:
        piece: The MIDI piece to analyze.
        default_bpm: Fallback BPM if estimation fails.

    Returns:
        Estimated tempo in BPM, clamped to [40, 240].
    """
    try:
        if piece.tracks:
            flat = mp.alg.concat(piece, mode='|').only_notes()
            if flat.notes:
                rhythm = mp.alg.analyze_rhythm(flat)
                # The rhythm object has beat information — use the most common gap
                ivs = getattr(flat, 'interval', [])
                if ivs:
                    most_common = max(set(ivs), key=ivs.count)
                    if 0.1 < most_common < 4.0:
                        bpm = 60.0 / most_common
                        return max(40.0, min(240.0, round(bpm, 1)))
    except Exception:
        pass
    return estimate_tempo(piece, default_bpm=default_bpm)


# ---------------------------------------------------------------------------
# Velocity normalization (no musicpy equivalent — keep handwritten)
# ---------------------------------------------------------------------------

def normalize_velocities(piece: mp.P, min_vel: int = 40, max_vel: int = 110) -> mp.P:
    """Normalize note velocities to a specified range.

    Performs linear rescaling of all note volumes across the entire piece.

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


# ---------------------------------------------------------------------------
# Simplified postprocessing — uses musicpy native APIs
# ---------------------------------------------------------------------------

def postprocess_midi(piece: mp.P,
                     min_vel: int = 40, max_vel: int = 110) -> mp.P:
    """Apply the simplified postprocessing pipeline.

    Handles tempo estimation and velocity normalization.
    Note: does NOT deduplicate notes here — the melody extraction
    pipeline handles cleaning upstream via _sustained_note_merge.

    Args:
        piece: The MIDI piece to process.
        min_vel: Minimum velocity for normalization.
        max_vel: Maximum velocity for normalization.

    Returns:
        The postprocessed MIDI piece.
    """
    result = piece.copy()

    # Tempo estimation + velocity normalization
    bpm = estimate_tempo(result)
    result.bpm = bpm
    result = normalize_velocities(result, min_vel=min_vel, max_vel=max_vel)

    return result


# ---------------------------------------------------------------------------
# Enhanced melody extraction pipeline — musicpy native + transcription glue
# ---------------------------------------------------------------------------

def extract_melody_pipeline(piece: mp.P, return_info: bool = False) -> mp.P | tuple[mp.P, dict]:
    """Extract clean melody from noisy audio transcription using musicpy.

    Pipeline:
    1. _sustained_note_merge — merge Basic Pitch transcription fragments
    2. pitch_filter(C3, C6) — restrict to reasonable melody range [musicpy]
    3. detect_scale2 — identify key/scale [musicpy]
    4. _filter_in_scale — remove out-of-key noise notes
    5. split_melody — extract main melody [musicpy]
    6. estimate_tempo + postprocess_midi — tempo and dynamics

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

    # Step 1: Merge transcription fragments into sustained notes
    result = _sustained_note_merge(piece)

    # Flatten to single chord for analysis
    concat_result = mp.alg.concat(result, mode='|')
    flat = concat_result.content if hasattr(concat_result, 'content') else concat_result
    info['notes_after_merge'] = len(flat.notes) if flat.notes else 0

    # Step 2: Filter to reasonable melody range (C3=48 to C6=84)
    if flat.notes:
        low = mp.note('C', 3)
        high = mp.note('C', 6)
        filtered = flat.pitch_filter(x=low, y=high)
        if filtered[0].notes:
            flat = filtered[0]

    info['notes_after_pitch_filter'] = len(flat) if flat.notes else 0

    # Step 3: Detect the key/scale (detect_scale2 is more robust to noise)
    scale_obj = None
    key_str = 'unknown'
    try:
        key_str = mp.alg.detect_scale2(flat)
        info['key'] = key_str

        # Parse the first scale name (e.g., "A major, F# minor" -> A major)
        first_scale = key_str.split(',')[0].strip()
        parts = first_scale.split()
        if len(parts) >= 2:
            scale_obj = mp.scale(start=mp.note(parts[0], 4), mode=parts[1])
    except Exception:
        info['key'] = 'unknown'

    # Step 4: Filter out notes not in the detected scale
    if scale_obj is not None and flat.notes:
        scale_degrees = set(n.degree % 12 for n in scale_obj)
        orig_intervals = getattr(flat, 'interval', [])
        notes_list = list(flat)
        # Use enumerate to track actual positions (avoids .index() ambiguity
        # when multiple notes share the same pitch)
        in_scale_notes: list[mp.note] = []
        original_indices: list[int] = []
        for idx, n in enumerate(notes_list):
            if (n.degree % 12) in scale_degrees:
                in_scale_notes.append(n)
                original_indices.append(idx)

        if len(in_scale_notes) > 1:
            cum_times: list[float] = [0.0]
            for i in range(1, len(original_indices)):
                cum_times.append(cum_times[-1] + sum(
                    orig_intervals[j] for j in range(original_indices[i - 1], original_indices[i])
                    if j < len(orig_intervals)
                ))
            new_intervals = [0.0] + [
                max(0.0, round(cum_times[i] - cum_times[i - 1], 4))
                for i in range(1, len(cum_times))
            ]
            flat = mp.chord(in_scale_notes, interval=new_intervals)

    info['notes_after_scale_filter'] = len(flat) if flat.notes else 0

    # Step 5: Extract melody using musicpy's split_melody
    try:
        if flat.notes:
            melody = mp.alg.split_melody(flat, mode='chord')
            if melody is not None and hasattr(melody, 'notes') and melody.notes:
                flat = melody
                info['notes_after_split_melody'] = len(flat)
    except Exception:
        pass

    # Step 5b: Second sustained-note merge after split_melody
    # (split_melody returns notes with proper intervals, but fragments still exist)
    if flat.notes:
        flat_piece = mp.P(tracks=[flat], instruments=[1], start_times=[0], bpm=120)
        flat_piece = _sustained_note_merge(flat_piece, window=0.35)
        if flat_piece.tracks:
            flat = flat_piece.tracks[0]
            info['notes_after_2nd_merge'] = len(flat.notes) if hasattr(flat, 'notes') else len(flat)

    # Step 6: Build single-track piece and postprocess
    bpm = estimate_tempo_enhanced(result)
    melody_piece = mp.P(
        tracks=[flat] if flat.notes else [flat],
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
