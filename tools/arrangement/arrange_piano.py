"""
Piano arrangement tool — simplified with musicpy.
"""

import musicpy as mp

from tools.analysis.extract_melody import ExtractMelodyTool
from tools.analysis.analyze_harmony import AnalyzeHarmonyTool
from tools.harmony.generate_accompaniment import GenerateAccompanimentTool

VALID_STYLES = {'classical', 'romantic', 'pop'}


class ArrangePianoTool:
    """Arrange any piece for piano solo."""

    name = "arrange_for_piano"
    description = (
        "Arrange a piece for piano solo. Extracts melody (RH) and "
        "generates accompaniment (LH). Styles: classical, romantic, pop."
    )

    def run(self, piece, style: str = 'classical',
            voicing: str = 'closed', hand_split: str = 'auto') -> mp.P.__class__:
        """Arrange for piano."""
        if style not in VALID_STYLES:
            raise ValueError(f"Invalid style '{style}'. Must be: {', '.join(sorted(VALID_STYLES))}")

        melody = ExtractMelodyTool().run(piece)
        harmony = AnalyzeHarmonyTool().run(piece, granularity='measure')

        pattern_map = {'classical': 'broken_chord', 'romantic': 'arpeggio', 'pop': 'block_chord'}
        accompaniment = GenerateAccompanimentTool().run(
            harmony, style=style, pattern=pattern_map[style], voicing=voicing,
        )

        result = mp.P(
            tracks=[melody, accompaniment],
            instruments=[1, 1],
            start_times=[0, 0],
            bpm=piece.bpm if piece.bpm else 120,
        )
        return result
