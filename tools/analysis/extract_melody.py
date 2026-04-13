"""
Melody extraction tool.

Merges high-pitched notes from all non-drum tracks to create
a continuous melody line that spans the full duration of the piece.
"""

import musicpy as mp


class ExtractMelodyTool:
    """Extract the primary melody from a multi-track piece."""

    name = "extract_melody"
    description = (
        "Extract the primary melody track from a piece. "
        "Merges notes from all tracks, picking the highest-pitched note "
        "at each time position. Returns a chord object containing "
        "the melody notes with correct timing."
    )

    def run(self, piece, confidence: float = 0.7) -> mp.chord:
        """
        Extract melody from a piece.

        Args:
            piece: A musicpy piece object.
            confidence: Threshold for inclusion (0.0-1.0).
                       Higher = stricter, only the clearest melody notes.

        Returns:
            A chord object containing the melody notes with intervals.
        """
        if not piece.tracks:
            return mp.chord([])

        # Collect all notes with absolute start times from all non-drum tracks
        all_notes = []
        for track_idx, track_content in enumerate(piece.tracks):
            # Skip drum tracks (instrument 26+ or very short note durations)
            instrument = piece.instruments[track_idx] if track_idx < len(piece.instruments) else 0
            if instrument >= 128:  # Channel 10 drums
                continue

            notes = track_content.notes if hasattr(track_content, 'notes') else list(track_content)
            if not notes:
                continue

            intervals = getattr(track_content, 'interval', None)
            # Skip very sparse tracks (likely percussion)
            total_dur = sum(getattr(n, 'duration', 0.25) for n in notes)
            if total_dur < 1.0:
                continue

            # Compute absolute start times
            pos = 0.0
            for j, n in enumerate(notes):
                iv = intervals[j] if intervals and j < len(intervals) else 0
                pos += iv
                if hasattr(n, 'degree'):
                    all_notes.append((pos, n))

        if not all_notes:
            return mp.chord([])

        # Sort by time
        all_notes.sort(key=lambda x: x[0])

        # Group notes that start at the same time (within tolerance)
        groups = _group_by_time(all_notes, tolerance=0.02)

        # For each group, take the highest-pitched note as melody
        melody_notes = []
        melody_intervals = []

        for group in groups:
            # Filter: only consider notes in the melody register (degree >= 60, C4+)
            # This filters out bass/harmony notes
            melody_candidates = [n for _, n in group if hasattr(n, 'degree') and n.degree >= 60]
            if not melody_candidates:
                # If no notes in melody register, skip this time position
                continue

            highest = max(melody_candidates, key=lambda n: n.degree)
            start_time = group[0][0]

            if melody_notes:
                melody_intervals.append(start_time - prev_time)
            else:
                melody_intervals.append(0.0)

            melody_notes.append(highest)
            prev_time = start_time

        if not melody_notes:
            return mp.chord([])

        # Apply confidence filter if requested
        if confidence > 0.5 and len(melody_notes) > 10:
            melody_notes, melody_intervals = _filter_outliers(
                melody_notes, melody_intervals, confidence
            )

        return mp.chord(melody_notes, interval=melody_intervals)


def _group_by_time(notes_with_time, tolerance=0.02):
    """Group notes by start time, within a small tolerance."""
    if not notes_with_time:
        return []

    groups = []
    current_group = [notes_with_time[0]]

    for item in notes_with_time[1:]:
        t = item[0]
        group_start = current_group[0][0]
        if abs(t - group_start) <= tolerance:
            current_group.append(item)
        else:
            groups.append(current_group)
            current_group = [item]
    groups.append(current_group)
    return groups


def _filter_outliers(melody_notes, melody_intervals, confidence):
    """Remove outlier notes that are too far from the average pitch."""
    degrees = [n.degree for n in melody_notes if hasattr(n, 'degree')]
    if not degrees:
        return melody_notes, melody_intervals

    avg = sum(degrees) / len(degrees)
    std = (sum((d - avg) ** 2 for d in degrees) / len(degrees)) ** 0.5
    threshold = std * (1.0 / (confidence - 0.5)) if confidence > 0.5 else float('inf')

    filtered_notes = []
    filtered_intervals = []

    for i, n in enumerate(melody_notes):
        if abs(n.degree - avg) <= threshold:
            filtered_notes.append(n)
            filtered_intervals.append(melody_intervals[i])

    if len(filtered_notes) < 2:
        return melody_notes, melody_intervals

    return filtered_notes, filtered_intervals
