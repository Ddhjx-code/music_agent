"""
Melody extraction tool.

Identifies the primary melody track from a multi-track piece
using pitch height, note density, and continuity heuristics.
"""

import musicpy as mp


class ExtractMelodyTool:
    """Extract the primary melody from a multi-track piece."""

    name = "extract_melody"
    description = (
        "Extract the primary melody track from a piece. "
        "Uses pitch height, note density, and continuity to identify "
        "the most likely melody track. Returns a chord object containing "
        "the melody notes."
    )

    def run(self, piece, confidence: float = 0.7) -> mp.chord:
        """
        Extract melody from a piece.

        Args:
            piece: A musicpy piece object.
            confidence: Threshold for inclusion (0.0-1.0).
                       Higher = stricter, only the clearest melody notes.

        Returns:
            A chord object containing the melody notes.
        """
        if not piece.tracks:
            return mp.chord([])

        # Score each track for "melody-ness"
        track_scores = []
        for i, track_content in enumerate(piece.tracks):
            notes = track_content.notes if hasattr(track_content, 'notes') else list(track_content)
            degrees = [n.degree for n in notes if hasattr(n, 'degree')]

            if not degrees:
                track_scores.append((i, 0.0, notes))
                continue

            # Pitch height score: melody tends to be in higher register
            avg_pitch = sum(degrees) / len(degrees)
            pitch_score = min(avg_pitch / 84.0, 1.0)  # Normalize to C6=84

            # Density score: melody has moderate density (not too sparse, not too dense)
            density = len(degrees)
            density_score = min(density / 20.0, 1.0)

            # Continuity score: check if notes form a continuous line
            if len(degrees) > 1:
                intervals = [abs(degrees[j+1] - degrees[j]) for j in range(len(degrees) - 1)]
                avg_interval = sum(intervals) / len(intervals)
                # Small intervals = more melodic/continuous
                continuity_score = max(0, 1.0 - avg_interval / 24.0)
            else:
                continuity_score = 0.5

            # Weighted combination
            score = 0.4 * pitch_score + 0.3 * density_score + 0.3 * continuity_score
            track_scores.append((i, score, notes))

        # Pick the track with highest melody score
        best_track_idx = max(track_scores, key=lambda x: x[1])[0]
        best_notes = track_scores[best_track_idx][2]

        # Apply confidence filter: remove notes that are outliers
        if confidence > 0.5 and best_notes:
            degrees = [n.degree for n in best_notes if hasattr(n, 'degree')]
            if degrees:
                avg = sum(degrees) / len(degrees)
                std = (sum((d - avg) ** 2 for d in degrees) / len(degrees)) ** 0.5
                threshold = std * (1.0 / (confidence - 0.5)) if confidence > 0.5 else float('inf')
                filtered = [
                    n for n in best_notes
                    if not hasattr(n, 'degree') or abs(n.degree - avg) <= threshold
                ]
                return mp.chord(filtered)

        return mp.chord(best_notes)
