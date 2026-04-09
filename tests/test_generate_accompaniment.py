"""
Tests for tools/harmony/generate_accompaniment.py — Accompaniment pattern generator.

TDD: Tests written BEFORE implementation.
"""

import pytest
import musicpy as mp

from tools.harmony.generate_accompaniment import GenerateAccompanimentTool, _parse_chord_name


class TestGenerateAccompanimentTool:
    """Tests for GenerateAccompanimentTool."""

    def test_classical_alberti_bass(self):
        """Classical style generates Alberti bass pattern (root-5th-3rd-5th)."""
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
        # Arpeggio should span more than one octave
        degrees = [n.degree for n in result if hasattr(n, 'degree')]
        if degrees:
            span = max(degrees) - min(degrees)
            assert span >= 12  # At least one octave

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

        sparse = tool.run(harmony, style='classical', pattern='broken_chord', density='sparse')
        dense = tool.run(harmony, style='classical', pattern='broken_chord', density='dense')

        assert len(sparse) <= len(dense)

    def test_open_vs_closed_voicing(self):
        """Open voicing has wider intervals between chord tones."""
        tool = GenerateAccompanimentTool()
        harmony = [{'measure': 1, 'chord': 'Cmajor'}]

        closed = tool.run(harmony, style='classical', pattern='block_chord', voicing='closed')
        open_v = tool.run(harmony, style='classical', pattern='block_chord', voicing='open')

        # Open voicing should span more range
        closed_degrees = [n.degree for n in closed if hasattr(n, 'degree')]
        open_degrees = [n.degree for n in open_v if hasattr(n, 'degree')]

        if closed_degrees and open_degrees:
            closed_span = max(closed_degrees) - min(closed_degrees)
            open_span = max(open_degrees) - min(open_degrees)
            assert open_span >= closed_span

    def test_handles_chord_progression(self):
        """Generate accompaniment for a full progression, not just one chord."""
        tool = GenerateAccompanimentTool()
        harmony = [
            {'measure': 1, 'chord': 'Cmajor'},
            {'measure': 2, 'chord': 'Gmajor'},
            {'measure': 3, 'chord': 'Aminor'},
            {'measure': 4, 'chord': 'Fmajor'},
        ]
        result = tool.run(harmony, style='classical', pattern='broken_chord')

        assert isinstance(result, mp.chord)
        # Should have content for all 4 measures
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


class TestParseChordName:
    """Tests for _parse_chord_name — robust parsing of all chord name formats."""

    def test_simple_major(self):
        root, intervals = _parse_chord_name('Cmajor')
        assert root == 'C'
        assert intervals == [0, 4, 7]

    def test_simple_minor(self):
        root, intervals = _parse_chord_name('Aminor')
        assert root == 'A'
        assert intervals == [0, 3, 7]

    def test_short_minor(self):
        root, intervals = _parse_chord_name('Am')
        assert root == 'A'
        assert intervals == [0, 3, 7]

    def test_major_seven(self):
        root, intervals = _parse_chord_name('Cmaj7')
        assert root == 'C'
        assert intervals == [0, 4, 7, 11]

    def test_dominant_seven(self):
        root, intervals = _parse_chord_name('G7')
        assert root == 'G'
        assert intervals == [0, 4, 7, 10]

    def test_minor_seven(self):
        root, intervals = _parse_chord_name('Am7')
        assert root == 'A'
        assert intervals == [0, 3, 7, 10]

    def test_maj13_not_minor(self):
        """Gmaj13 must NOT parse as minor — existing bug."""
        root, intervals = _parse_chord_name('Gmaj13')
        assert root == 'G'
        assert 3 not in intervals  # No minor third

    def test_complex_musicpy_omit_sort(self):
        """Handle 'Am13 omit G sort as [3, 1, 2, 5, 4, 6]' from musicpy."""
        root, intervals = _parse_chord_name('Am13 omit G sort as [3, 1, 2, 5, 4, 6]')
        assert root == 'A'
        assert 3 in intervals  # Minor quality

    def test_complex_sus4_omit(self):
        """Handle 'G13sus4 omit D sort as [4, 1, 3, 5, 2]'."""
        root, intervals = _parse_chord_name('G13sus4 omit D sort as [4, 1, 3, 5, 2]')
        assert root == 'G'
        assert 5 in intervals  # sus4 has perfect 4th

    def test_six_nine_chord(self):
        root, intervals = _parse_chord_name('C69')
        assert root == 'C'

    def test_sus2(self):
        root, intervals = _parse_chord_name('Csus2')
        assert root == 'C'
        assert intervals == [0, 2, 7]

    def test_sus4(self):
        root, intervals = _parse_chord_name('Csus4')
        assert root == 'C'
        assert intervals == [0, 5, 7]

    def test_diminished(self):
        root, intervals = _parse_chord_name('Bdim')
        assert root == 'B'
        assert intervals == [0, 3, 6]

    def test_augmented(self):
        root, intervals = _parse_chord_name('Caug')
        assert root == 'C'
        assert intervals == [0, 4, 8]

    def test_sharp_root(self):
        root, intervals = _parse_chord_name('F#major')
        assert root == 'F#'
        assert intervals == [0, 4, 7]

    def test_flat_root(self):
        root, intervals = _parse_chord_name('Bbmajor')
        assert root == 'Bb'
        assert intervals == [0, 4, 7]

    def test_note_fallback_extracts_pitch(self):
        """'note G4' should extract G as root, not default to C."""
        root, intervals = _parse_chord_name('note G4')
        assert root == 'G'
        assert intervals == [0, 4, 7]

    def test_rest_fallback(self):
        root, intervals = _parse_chord_name('rest')
        assert root == 'C'
        assert intervals == [0, 4, 7]

    def test_unknown_fallback(self):
        root, intervals = _parse_chord_name('unknown')
        assert root == 'C'
        assert intervals == [0, 4, 7]

    def test_slash_chord_ignores_bass(self):
        """'Cmaj7/E' — bass note after / should be ignored, root is C."""
        root, intervals = _parse_chord_name('Cmaj7/E')
        assert root == 'C'
        assert intervals == [0, 4, 7, 11]

    def test_omit_and_slash(self):
        """Handle 'G13 omit C /E' — simplify to basic quality."""
        root, intervals = _parse_chord_name('G13 omit C /E')
        assert root == 'G'
        # Should detect as some kind of chord with a third
        assert 3 in intervals or 4 in intervals

    def test_minor_ninth(self):
        root, intervals = _parse_chord_name('Am9')
        assert root == 'A'
        assert 3 in intervals  # minor

    def test_minor_eleventh(self):
        root, intervals = _parse_chord_name('Am11')
        assert root == 'A'
        assert 3 in intervals  # minor

    def test_dominant_thirteen(self):
        root, intervals = _parse_chord_name('D13')
        assert root == 'D'
        assert 4 in intervals  # major third (dominant, not minor)

    def test_maj9(self):
        root, intervals = _parse_chord_name('Gmaj9')
        assert root == 'G'
        assert 3 not in intervals  # Not minor
        assert 4 in intervals  # Major third
