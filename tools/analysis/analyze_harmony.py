"""
Harmony analysis tool.

Analyzes chord progression from a piece using musicpy's alg.detect.
Groups notes by measure/time window across ALL tracks and detects
the chord for each group.
"""

import re

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
        """Detect chord from notes, returning structured result."""
        if not notes:
            return {'chord': 'rest', 'root': 'C', 'quality': 'rest'}

        try:
            chord_obj = mp.chord(notes)

            # Try structured detection first
            ct = mp.alg.detect_chord_by_root(chord_obj, get_chord_type=True)
            if ct is not None and ct.root is not None and ct.chord_type is not None:
                return {
                    'chord': f'{ct.root}{ct.chord_type}',
                    'root': ct.root,
                    'quality': ct.chord_type,
                }

            # If ct exists but root is None (single note), extract from note_name
            if ct is not None and getattr(ct, 'note_name', None):
                note_name = ct.note_name  # e.g., 'D4'
                root = self._extract_root(note_name)
                return {
                    'chord': f'{root}major',
                    'root': root,
                    'quality': 'major',
                }

            # Fallback: string detection with simplification
            raw = mp.alg.detect(chord_obj)
            simplified = self._simplify_chord_name(raw)
            root = self._extract_root(simplified)
            quality = self._extract_quality(simplified)
            return {
                'chord': simplified,
                'root': root,
                'quality': quality,
            }
        except Exception:
            return {'chord': 'unknown', 'root': 'C', 'quality': 'unknown'}

    def _simplify_chord_name(self, raw: str) -> str:
        """Simplify musicpy chord name string for downstream parsing."""
        if not raw:
            return 'unknown'
        if raw.startswith('note '):
            return raw

        # Handle polychord format: [X]/[Y] -> just use the first chord
        if raw.startswith('['):
            match = re.match(r'\[([^\]]+)\]', raw)
            if match:
                raw = match.group(1)

        # Remove 'sort as [...]' suffix (handle nested brackets too)
        result = re.sub(r'\s*sort\s+as\s+\[[^\]]*\]?', '', raw)
        # Remove 'omit X' clauses
        result = re.sub(r'\s*omit\s+\w+', '', result)
        # Remove slash bass notes (but not polychord slashes)
        result = re.sub(r'/[A-G][#b]?\s*$', '', result)
        # Simplify 'with X' format (e.g., 'D with perfect fourth' -> 'Dsus4')
        if ' with perfect fourth' in result:
            result = result.replace(' with perfect fourth', 'sus4')
        elif ' with major third' in result:
            result = result.replace(' with major third', 'major')
        elif ' with minor third' in result:
            result = result.replace(' with minor third', 'minor')
        elif ' with ' in result:
            # Generic 'with X' -> just use root
            match = re.match(r'^([A-G][#b]?)\s+with\s+', result)
            if match:
                result = match.group(1) + 'major'
        return result.strip()

    def _extract_root(self, chord_str: str) -> str:
        """Extract root note from a chord name string."""
        match = re.match(r'^(?:note\s+)?([A-G][#b]?)', chord_str)
        return match.group(1) if match else 'C'

    def _extract_quality(self, chord_str: str) -> str:
        """Extract quality keyword from a chord name string."""
        rest = re.sub(r'^(?:note\s+)?[A-G][#b]?', '', chord_str).strip().lower()
        rest = re.sub(r'/[A-G][#b]?\s*$', '', rest)
        rest = re.sub(r'\s*sort\s+as\s+\[.*?\]', '', rest)
        rest = re.sub(r'\s*omit\s+\w+', '', rest)
        return rest if rest else 'major'
