"""
Harmony analysis tool.

Analyzes chord progression from a piece using musicpy's alg.detect.
Groups notes by measure/time window and detects the chord for each group.
"""

import musicpy as mp


class AnalyzeHarmonyTool:
    """Analyze chord progression from a piece."""

    name = "analyze_harmony"
    description = (
        "Analyze the chord progression of a piece. Groups notes by measure "
        "and detects the chord for each group using musicpy's algorithm module. "
        "Returns a list of {measure, chord, root, quality} dicts."
    )

    def run(self, piece, granularity: str = "measure") -> list[dict]:
        """
        Analyze harmony in a piece.

        Args:
            piece: A musicpy piece object.
            granularity: 'measure' (default) or 'phrase'.
                        'measure' = one chord per measure (1.0 beat units).
                        'phrase' = one chord per 4 measures.

        Returns:
            List of dicts with keys: measure, chord.
        """
        window_size = 1.0 if granularity == "measure" else 4.0

        # Find the track with the most harmonic content (lowest pitch range, most notes)
        best_track = None
        best_score = -1
        for track_content in piece.tracks:
            notes = track_content.notes if hasattr(track_content, 'notes') else list(track_content)
            degrees = [n.degree for n in notes if hasattr(n, 'degree')]
            if not degrees:
                continue
            # Prefer tracks with moderate pitch range (harmony tracks)
            avg_pitch = sum(degrees) / len(degrees) if degrees else 0
            # Score: prefer tracks with more notes in the middle register
            score = len(degrees) * (1.0 - abs(avg_pitch - 60) / 60.0)
            if score > best_score:
                best_score = score
                best_track = notes

        if best_track is None:
            return []

        # Group notes by time window
        current_pos = 0.0
        current_group = []
        measure_num = 1
        progression = []

        for note in best_track:
            duration = getattr(note, 'duration', 0.25)
            current_group.append(note)
            current_pos += duration

            if current_pos >= window_size:
                chord_name = self._detect_chord(current_group)
                progression.append({
                    'measure': measure_num,
                    'chord': chord_name,
                })
                measure_num += 1
                current_group = []
                current_pos = 0.0

        # Handle remaining notes
        if current_group:
            chord_name = self._detect_chord(current_group)
            progression.append({
                'measure': measure_num,
                'chord': chord_name,
            })

        return progression

    def _detect_chord(self, notes) -> str:
        """Detect chord type from a list of notes."""
        if not notes:
            return 'rest'

        try:
            chord_obj = mp.chord(notes)
            result = mp.alg.detect(chord_obj)
            return result if result else 'unknown'
        except Exception:
            return 'unknown'
