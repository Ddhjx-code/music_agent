"""
Velocity adjustment tool.

Adjusts note velocities (volumes) to create dynamic contrast:
- Boost melody track velocity
- Reduce accompaniment track velocity
This creates clearer melody/accompaniment separation in the mix.
"""

import musicpy as mp

from tools.analysis.voice_detection import detect_voice_roles


class AdjustVelocityTool:
    """Adjust note velocities for dynamic balance."""

    name = "adjust_velocity"
    description = (
        "Adjust note velocities to create dynamic contrast between "
        "melody and accompaniment. "
        "Args: melody_boost (int) - velocity increase for melody track (default 0), "
        "accompaniment_reduce (int) - velocity decrease for accompaniment tracks (default 0). "
        "Returns the piece with adjusted velocities."
    )

    def run(self, piece, melody_boost: int = 0,
            accompaniment_reduce: int = 0) -> mp.P.__class__:
        """
        Adjust note velocities.

        Args:
            piece: A musicpy piece object.
            melody_boost: Amount to add to melody track velocity.
            accompaniment_reduce: Amount to subtract from accompaniment tracks.

        Returns:
            The piece with adjusted velocities.
        """
        if not piece.tracks or (melody_boost == 0 and accompaniment_reduce == 0):
            return piece

        result = piece.copy()
        roles = detect_voice_roles(piece)
        melody_indices = set(roles.get('melody', []))

        for track_idx, track in enumerate(result.tracks):
            notes = track.notes if hasattr(track, 'notes') else list(track)
            if track_idx in melody_indices:
                adjustment = melody_boost
            else:
                adjustment = -accompaniment_reduce

            for note in notes:
                if hasattr(note, 'volume'):
                    new_vel = note.volume + adjustment
                    note.volume = max(1, min(127, new_vel))

        return result
