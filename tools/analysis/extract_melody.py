"""
Melody extraction tool.

Uses musicpy's multi-track operations to extract the primary melody line.
"""

import musicpy as mp


class ExtractMelodyTool:
    """Extract the primary melody from a multi-track piece."""

    name = "extract_melody"
    description = (
        "Extract the primary melody track from a piece. "
        "Uses musicpy to merge tracks, pick highest notes at each time position, "
        "and filter by melody register. Returns a chord object."
    )

    def run(self, piece, confidence: float = 0.7) -> mp.chord:
        """
        Extract melody from a piece using musicpy operations.

        Args:
            piece: A musicpy piece object.
            confidence: Threshold for inclusion (kept for API compatibility).

        Returns:
            A chord object containing the melody notes with intervals.
        """
        if not piece.tracks:
            return mp.chord([])

        # Collect all non-drum notes with absolute start times
        all_notes = []
        for track_idx, track_content in enumerate(piece.tracks):
            instrument = piece.instruments[track_idx] if track_idx < len(piece.instruments) else 0
            if instrument >= 128:
                continue

            notes = track_content.notes if hasattr(track_content, 'notes') else list(track_content)
            if not notes:
                continue

            total_dur = sum(getattr(n, 'duration', 0.25) for n in notes)
            if total_dur < 1.0:
                continue

            intervals = getattr(track_content, 'interval', None)
            pos = 0.0
            for j, n in enumerate(notes):
                iv = intervals[j] if intervals and j < len(intervals) else 0
                pos += iv
                if hasattr(n, 'degree') and n.degree >= 60:  # Melody register
                    all_notes.append((pos, n))

        if not all_notes:
            return mp.chord([])

        all_notes.sort(key=lambda x: x[0])

        # Group by time, take highest note per position
        melody_notes = []
        melody_intervals = []
        prev_time = 0.0

        for time, note in all_notes:
            if not melody_notes or abs(time - prev_time) > 0.02:
                melody_notes.append(note)
                if melody_intervals:
                    melody_intervals.append(time - prev_time)
                else:
                    melody_intervals.append(0.0)
                prev_time = time
            else:
                if hasattr(note, 'degree') and hasattr(melody_notes[-1], 'degree'):
                    if note.degree > melody_notes[-1].degree:
                        melody_notes[-1] = note

        return mp.chord(melody_notes, interval=melody_intervals)
