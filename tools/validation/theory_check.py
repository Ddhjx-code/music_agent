"""
Theory validation tool.

Aggregates multiple validation checks:
1. Instrument range (reuses RangeCheckTool)
2. Voice leading (parallel fifths/octaves detection)
3. Harmony consistency (unresolved dissonance check)

Returns structured issues that the LLM can use for self-correction.
"""

import musicpy as mp

from tools.validation.range_check import RangeCheckTool, INSTRUMENT_RANGES


# GM program → instrument name mapping
_PROGRAM_TO_INSTRUMENT = {
    1: 'piano',      # Acoustic Grand Piano
    40: 'violin',    # Violin
    41: 'viola',     # Viola
    42: 'cello',     # Cello
    53: 'tuba',      # Tuba
    56: 'trumpet',   # Trumpet
    57: 'trombone',  # Trombone
    60: 'french_horn',  # French Horn
    65: 'alto_sax',  # Alto Sax
    71: 'clarinet',  # Clarinet
    74: 'flute',     # Flute
}


def _check_voice_leading(piece) -> list[dict]:
    """Check for parallel perfect fifths and octaves between adjacent tracks."""
    issues = []
    if len(piece.tracks) < 2:
        return issues

    for i in range(len(piece.tracks) - 1):
        notes_a = [n for n in piece.tracks[i] if hasattr(n, 'degree')]
        notes_b = [n for n in piece.tracks[i + 1] if hasattr(n, 'degree')]
        if not notes_a or not notes_b:
            continue

        prev_interval = None
        for j in range(min(len(notes_a), len(notes_b))):
            interval = notes_a[j].degree - notes_b[j].degree
            if prev_interval is not None:
                if abs(prev_interval) == 7 and abs(interval) == 7:
                    issues.append({
                        'type': 'parallel_fifth',
                        'tracks': [i, i + 1],
                        'position': j,
                        'severity': 'warning',
                    })
                elif abs(prev_interval) == 12 and abs(interval) == 12:
                    issues.append({
                        'type': 'parallel_octave',
                        'tracks': [i, i + 1],
                        'position': j,
                        'severity': 'warning',
                    })
            prev_interval = interval

    return issues


def _check_harmony(piece) -> list[dict]:
    """Check for extreme dissonance: clusters of adjacent semitones."""
    issues = []
    for track_idx, track in enumerate(piece.tracks):
        notes = track.notes if hasattr(track, 'notes') else list(track)
        degrees = sorted(n.degree for n in notes if hasattr(n, 'degree'))
        if len(degrees) < 3:
            continue
        # Check for clusters: 3+ consecutive semitones
        cluster_len = 1
        for k in range(1, len(degrees)):
            if degrees[k] == degrees[k - 1] + 1:
                cluster_len += 1
            else:
                if cluster_len >= 3:
                    issues.append({
                        'type': 'tone_cluster',
                        'track': track_idx,
                        'start_note': degrees[k - cluster_len],
                        'length': cluster_len,
                        'severity': 'warning',
                    })
                cluster_len = 1
        # Check final cluster
        if cluster_len >= 3:
            issues.append({
                'type': 'tone_cluster',
                'track': track_idx,
                'start_note': degrees[-cluster_len],
                'length': cluster_len,
                'severity': 'warning',
            })

    return issues


class ValidateTheoryTool:
    """Comprehensive music theory validation."""

    name = "validate_theory"
    description = (
        "Comprehensive validation: instrument ranges, voice leading "
        "(parallel fifths/octaves), and harmony consistency. "
        "Args: instrument (str) - target instrument for range check (default 'piano'). "
        "Returns {passed: bool, issues: list[dict], summary: str}."
    )

    def run(self, piece, instrument: str = 'piano') -> dict:
        """
        Run all validation checks.

        Args:
            piece: A musicpy piece object.
            instrument: Target instrument name for range checking.

        Returns:
            Dict with 'passed', 'issues' (list), and 'summary' (str).
        """
        all_issues = []

        # 1. Range check
        range_result = RangeCheckTool().run(piece, instrument=instrument)
        if not range_result['passed']:
            all_issues.extend([
                {**issue, 'severity': 'error'}
                for issue in range_result['issues']
            ])

        # 2. Voice leading
        vl_issues = _check_voice_leading(piece)
        all_issues.extend(vl_issues)

        # 3. Harmony
        h_issues = _check_harmony(piece)
        all_issues.extend(h_issues)

        has_errors = any(i.get('severity') == 'error' for i in all_issues)
        return {
            'passed': not has_errors,
            'issues': all_issues,
            'summary': self._summarize(all_issues),
        }

    def _summarize(self, issues: list[dict]) -> str:
        if not issues:
            return "All checks passed."
        by_type = {}
        for issue in issues:
            t = issue.get('type', 'unknown')
            by_type[t] = by_type.get(t, 0) + 1
        parts = []
        for t, count in by_type.items():
            parts.append(f"{count} {t}")
        return f"Validation issues: {', '.join(parts)}"
