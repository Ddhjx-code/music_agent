"""
Timing variation tool.

Applies subtle timing variations to simulate human performance:
- rubato: Micro slowing at phrase endings (expressive deceleration)
- swing: Unequal eighth notes (long-short pattern)
"""

import random

import musicpy as mp

# Reproducible randomness
random.seed(42)


class ApplyTimingVariationTool:
    """Apply timing variation to a piece."""

    name = "apply_timing_variation"
    description = (
        "Apply subtle timing variation to simulate human performance. "
        "Args: type (str) - 'rubato' (phrase-end deceleration) or 'swing' "
        "(unequal eighth notes), amount (float) - variation intensity (0.01-0.2). "
        "Returns the piece with modified note timing intervals."
    )

    VALID_TYPES = {'rubato', 'swing'}

    def run(self, piece, type: str = 'rubato',
            amount: float = 0.05) -> mp.P.__class__:
        """
        Apply timing variation.

        Args:
            piece: A musicpy piece object.
            type: 'rubato' or 'swing'.
            amount: Variation intensity (0.01-0.2 recommended).

        Returns:
            The piece with modified timing.
        """
        if type not in self.VALID_TYPES:
            raise ValueError(f"Invalid type: {type}. Must be one of: {self.VALID_TYPES}")

        if not piece.tracks:
            return piece

        result = piece.copy()

        for track_idx, track in enumerate(result.tracks):
            intervals = getattr(track, 'interval', None)
            if not intervals:
                continue
            notes = track.notes if hasattr(track, 'notes') else list(track)
            if not notes:
                continue

            new_intervals = list(intervals)

            if type == 'rubato':
                new_intervals = self._apply_rubato(notes, new_intervals, amount)
            elif type == 'swing':
                new_intervals = self._apply_swing(new_intervals, amount)

            track.interval = new_intervals

        return result

    def _apply_rubato(self, notes, intervals, amount):
        """Apply expressive deceleration at phrase boundaries."""
        if not intervals:
            return intervals

        result = list(intervals)
        n = len(result)
        if n < 2:
            return result

        # Identify phrase boundaries: gaps longer than average
        avg_interval = sum(result) / len(result)
        phrase_threshold = avg_interval * 2.0

        for i in range(n):
            is_gap = result[i] > phrase_threshold
            is_phrase_end = (i > 0 and i % 8 == 7)  # Every 8th note
            is_last = (i == n - 1)

            if is_gap or is_phrase_end or is_last:
                # Slow down: increase the interval
                slowdown = 1.0 + amount * (0.5 + random.random() * 0.5)
                result[i] = result[i] * slowdown
                # Speed up the previous note slightly (compensatory)
                if i > 0:
                    speedup = 1.0 - amount * 0.3
                    result[i - 1] = max(0.01, result[i - 1] * speedup)

        return result

    def _apply_swing(self, intervals, amount):
        """Apply swing feel: even-numbered eighth notes become long-short."""
        if not intervals:
            return intervals

        result = list(intervals)
        swing_ratio = 0.5 + amount  # 0.5 = even, 0.65 = swing

        for i in range(0, len(result) - 1, 2):
            # Pair of intervals
            total = result[i] + result[i + 1]
            result[i] = total * swing_ratio
            result[i + 1] = total * (1.0 - swing_ratio)

        return result
