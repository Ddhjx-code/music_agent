"""
Tests for tools/harmony/generate_accompaniment.py — Accompaniment pattern generator.
"""

import pytest
import musicpy as mp

from tools.harmony.generate_accompaniment import GenerateAccompanimentTool


class TestGenerateAccompanimentTool:
    """Tests for GenerateAccompanimentTool."""

    def test_classical_alberti_bass(self):
        """Classical style generates broken chord / Alberti bass pattern."""
        tool = GenerateAccompanimentTool()
        harmony = [{'measure': 1, 'chord': 'Cmajor'}]
        result = tool.run(harmony, style='classical', pattern='broken_chord')

        assert isinstance(result, mp.chord)
        assert len(result) > 0

    def test_romantic_arpeggio(self):
        """Romantic style generates wide arpeggios spanning >1 octave."""
        tool = GenerateAccompanimentTool()
        harmony = [{'measure': 1, 'chord': 'Cmajor'}]
        result = tool.run(harmony, style='romantic', pattern='arpeggio')

        assert isinstance(result, mp.chord)
        degrees = [n.degree for n in result if hasattr(n, 'degree')]
        if degrees:
            span = max(degrees) - min(degrees)
            assert span >= 12

    def test_pop_block_chord(self):
        """Pop style generates block chords with octave bass."""
        tool = GenerateAccompanimentTool()
        harmony = [{'measure': 1, 'chord': 'Cmajor'}]
        result = tool.run(harmony, style='pop', pattern='block_chord')

        assert isinstance(result, mp.chord)
        assert len(result) > 0

    def test_density_sparse(self):
        """Sparse density produces fewer notes."""
        tool = GenerateAccompanimentTool()
        harmony = [{'measure': 1, 'chord': 'Cmajor'}]

        sparse = tool.run(harmony, style='classical', pattern='arpeggio', density='sparse')
        dense = tool.run(harmony, style='classical', pattern='arpeggio', density='dense')

        assert len(sparse) <= len(dense)

    def test_open_vs_closed_voicing(self):
        """Open voicing has wider intervals between chord tones."""
        tool = GenerateAccompanimentTool()
        harmony = [{'measure': 1, 'chord': 'Cmajor'}]

        closed = tool.run(harmony, style='classical', pattern='arpeggio', voicing='closed')
        open_v = tool.run(harmony, style='classical', pattern='arpeggio', voicing='open')

        closed_degrees = [n.degree for n in closed if hasattr(n, 'degree')]
        open_degrees = [n.degree for n in open_v if hasattr(n, 'degree')]

        if closed_degrees and open_degrees:
            closed_span = max(closed_degrees) - min(closed_degrees)
            open_span = max(open_degrees) - min(open_degrees)
            assert open_span >= closed_span

    def test_handles_chord_progression(self):
        """Generate accompaniment for a full progression."""
        tool = GenerateAccompanimentTool()
        harmony = [
            {'measure': 1, 'chord': 'Cmajor'},
            {'measure': 2, 'chord': 'Gmajor'},
            {'measure': 3, 'chord': 'Aminor'},
            {'measure': 4, 'chord': 'Fmajor'},
        ]
        result = tool.run(harmony, style='classical', pattern='broken_chord')

        assert isinstance(result, mp.chord)
        assert len(result) >= 4

    def test_output_is_chord_object(self):
        """Return type is always musicpy chord."""
        tool = GenerateAccompanimentTool()
        harmony = [{'measure': 1, 'chord': 'Cmajor'}]

        for style in ['classical', 'romantic', 'pop']:
            result = tool.run(harmony, style=style, pattern='broken_chord')
            assert isinstance(result, mp.chord), f"Failed for style: {style}"

    def test_empty_harmony(self):
        """Empty harmony returns empty chord."""
        tool = GenerateAccompanimentTool()
        result = tool.run([], style='classical', pattern='broken_chord')

        assert isinstance(result, mp.chord)
        assert len(result) == 0

    def test_unknown_chord_fallback(self):
        """Unknown chord names don't crash the tool."""
        tool = GenerateAccompanimentTool()
        harmony = [{'measure': 1, 'chord': 'Xmajor13b5#9'}]
        result = tool.run(harmony, style='classical', pattern='broken_chord')

        assert isinstance(result, mp.chord)
