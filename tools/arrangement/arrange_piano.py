"""
Piano arrangement tool — decoupled version.

Accepts pre-extracted melody and harmony data from Analyst.
No longer calls ExtractMelodyTool or AnalyzeHarmonyTool internally.
"""

import musicpy as mp

from tools.harmony.generate_accompaniment import GenerateAccompanimentTool

VALID_STYLES = {'classical', 'romantic', 'pop'}


class ArrangePianoTool:
    """Arrange any piece for piano solo."""

    name = "arrange_for_piano"
    description = (
        "Arrange a piece for piano solo using pre-extracted melody (RH) "
        "and harmony data to generate accompaniment (LH). "
        "Styles: classical, romantic, pop."
    )

    def run(self, piece, melody: mp.chord, harmony: list[dict],
            style: str = 'classical',
            voicing: str = 'closed') -> mp.P:
        """Arrange for piano using pre-extracted melody and harmony."""
        if style not in VALID_STYLES:
            raise ValueError(
                f"Invalid style '{style}'. Must be: {', '.join(sorted(VALID_STYLES))}"
            )

        pattern_map = {
            'classical': 'broken_chord',
            'romantic': 'arpeggio',
            'pop': 'block_chord',
        }
        accompaniment = GenerateAccompanimentTool().run(
            harmony,
            style=style,
            pattern=pattern_map[style],
            voicing=voicing,
        )

        result = mp.P(
            tracks=[melody, accompaniment],
            instruments=[1, 1],
            start_times=[0, 0],
            bpm=piece.bpm if piece.bpm else 120,
        )
        return result
