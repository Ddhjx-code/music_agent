"""
Harmony analysis tool.

Analyzes chord progression from a piece using musicpy's alg.detect.
Groups notes by measure/time window across ALL tracks and detects
the chord for each group.
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
            List of dicts with keys: measure, chord, root, quality.
        """
        window_size = 1.0 if granularity == "measure" else 4.0

        # Collect all notes from all valid tracks, tagged with actual start time.
        timed_notes = []
        for track_content in piece.tracks:
            track_notes = track_content.notes if hasattr(track_content, 'notes') else list(track_content)
            if not track_notes:
                continue

            total_dur = sum(getattr(n, 'duration', 0.25) for n in track_notes)
            if total_dur < 1.0:
                continue

            # Compute actual start times from the chord's interval attribute
            start_times = self._get_start_times(track_content, track_notes)
            for note, st in zip(track_notes, start_times):
                timed_notes.append((st, note))

        if not timed_notes:
            return []

        # Sort by start time
        timed_notes.sort(key=lambda x: x[0])

        # Group notes by time window, collecting from ALL tracks
        progression = []
        measure_num = 1
        max_time = timed_notes[-1][0]
        window_start = 0.0

        while window_start <= max_time:
            window_end = window_start + window_size
            window_notes = [n for t, n in timed_notes
                            if window_start <= t < window_end]

            if window_notes:
                entry = self._detect_chord(window_notes)
                entry['measure'] = measure_num
                progression.append(entry)
                measure_num += 1

            window_start = window_end

        return progression

    def _get_start_times(self, track_content, notes):
        """Compute actual start times for notes in a track/chord."""
        intervals = getattr(track_content, 'interval', None)
        if intervals is None or len(intervals) != len(notes):
            # Fallback: sequential timing
            times = []
            current = 0.0
            for n in notes:
                times.append(current)
                current += getattr(n, 'duration', 0.25)
            return times
        return list(intervals)

    def _detect_chord(self, notes) -> dict:
        """Detect chord from notes using musicpy alg.detect."""
        if not notes:
            return {'chord': 'rest', 'root': 'C', 'quality': 'rest'}

        try:
            chord_obj = mp.chord(notes)

            # Try structured detection first
            ct = mp.alg.detect_chord_by_root(chord_obj, get_chord_type=True)
            if ct and ct.root and ct.chord_type:
                return {
                    'chord': f'{ct.root}{ct.chord_type}',
                    'root': ct.root,
                    'quality': ct.chord_type,
                }

            if ct and getattr(ct, 'note_name', None):
                root = ct.note_name[:-1]  # e.g., 'D4' -> 'D'
                return {'chord': f'{root}major', 'root': root, 'quality': 'major'}

            # Fallback: string detection, minimal cleanup
            raw = mp.alg.detect(chord_obj)
            root = self._extract_root(raw)
            return {'chord': raw, 'root': root, 'quality': raw.replace(root, '') or 'major'}

        except Exception:
            return {'chord': 'unknown', 'root': 'C', 'quality': 'unknown'}

    def _extract_root(self, chord_str: str) -> str:
        """Extract root note from a chord name string."""
        import re
        match = re.match(r'^(?:note\s+)?([A-G][#b]?)', chord_str)
        return match.group(1) if match else 'C'
