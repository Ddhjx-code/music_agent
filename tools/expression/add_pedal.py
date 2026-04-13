"""
Sustain pedal tool.

Inserts CC#64 (sustain pedal) events into a piece at harmonic
change points to add expression and legato phrasing.

mode='harmonic_change': pedal down at each chord change, up before next
mode='every_measure': pedal down at each measure boundary
"""

import musicpy as mp

from tools.analysis.analyze_harmony import AnalyzeHarmonyTool


class AddSustainPedalTool:
    """Insert sustain pedal events into a piece."""

    name = "add_sustain_pedal"
    description = (
        "Insert CC#64 sustain pedal events into a piece. "
        "Pedal down (value=127) at harmonic change points, pedal off (value=0) "
        "before the next change. "
        "Args: mode (str) - 'harmonic_change' (default) or 'every_measure'. "
        "Returns the piece with pedal events in other_messages."
    )

    def run(self, piece, mode: str = 'harmonic_change') -> mp.P.__class__:
        """
        Add sustain pedal events to a piece.

        Args:
            piece: A musicpy piece object.
            mode: 'harmonic_change' or 'every_measure'.

        Returns:
            The piece with sustain pedal events added.
        """
        if not piece.tracks:
            return piece

        result = piece.copy()
        pedal_events = []

        if mode == 'harmonic_change':
            harmony = AnalyzeHarmonyTool().run(piece, granularity='measure')
            for entry in harmony:
                measure = entry.get('measure', 1)
                beat = (measure - 1) * 4.0  # Assuming 4/4

                # Pedal on at chord change
                pedal_events.append(mp.event(
                    'control_change',
                    channel=0,
                    control=64,
                    value=127,
                    track=0,
                    start_time=beat,
                ))

                # Pedal off before next chord (slightly before next measure)
                pedal_off = beat + 3.9  # Release just before next chord
                pedal_events.append(mp.event(
                    'control_change',
                    channel=0,
                    control=64,
                    value=0,
                    track=0,
                    start_time=pedal_off,
                ))

        elif mode == 'every_measure':
            # Add pedal on at every measure boundary
            total_beats = self._total_beats(piece)
            beats_per_measure = 4.0  # Assuming 4/4
            n_measures = int(total_beats / beats_per_measure) + 1

            for m in range(n_measures):
                beat = m * beats_per_measure
                pedal_events.append(mp.event(
                    'control_change',
                    channel=0,
                    control=64,
                    value=127,
                    track=0,
                    start_time=beat,
                ))
                pedal_events.append(mp.event(
                    'control_change',
                    channel=0,
                    control=64,
                    value=0,
                    track=0,
                    start_time=beat + beats_per_measure - 0.1,
                ))
        else:
            raise ValueError(f"Invalid mode: {mode}. Use 'harmonic_change' or 'every_measure'.")

        # Attach pedal events to the piece
        result.other_messages = list(getattr(result, 'other_messages', [])) + pedal_events
        return result

    def _total_beats(self, piece) -> float:
        """Estimate total beats from all tracks."""
        max_beats = 0.0
        for track in piece.tracks:
            notes = track.notes if hasattr(track, 'notes') else list(track)
            intervals = getattr(track, 'interval', [])
            if notes and intervals:
                total = sum(intervals)
                last_note_dur = getattr(notes[-1], 'duration', 0.25)
                max_beats = max(max_beats, total + last_note_dur)
        return max_beats
