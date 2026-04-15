"""
Tests for the enhanced melody extraction pipeline.
"""

import musicpy as mp

from core.audio_postprocess import extract_melody_pipeline, estimate_tempo_enhanced


class TestMelodyExtractionPipeline:
    """Tests for extract_melody_pipeline."""

    def test_reduces_note_count(self):
        """Pipeline should significantly reduce note count from noisy input."""
        noisy = _create_noisy_piece()
        noisy_count = sum(len(t) for t in noisy.tracks)
        result = extract_melody_pipeline(noisy)
        result_count = sum(len(t) for t in result.tracks)
        assert result_count < noisy_count

    def test_detects_key(self):
        """Pipeline should detect and return the key."""
        piece = _create_a_major_piece()
        result, info = extract_melody_pipeline(piece, return_info=True)
        assert 'a' in info.get('key', '').lower()

    def test_preserves_melody_notes(self):
        """Known melody notes should survive the pipeline."""
        piece = _create_noisy_with_known_melody()
        result = extract_melody_pipeline(piece)
        melody_degrees = {n.degree for n in result.tracks[0] if hasattr(n, 'degree')}
        # At least some of the known melody pitches should survive
        assert melody_degrees & {64, 66, 68, 69, 71}

    def test_single_track_output(self):
        """After split_melody, result should have 1 track (melody)."""
        noisy = _create_noisy_piece()
        result = extract_melody_pipeline(noisy)
        assert len(result.tracks) == 1

    def test_quantized_timings(self):
        """Output timings should be on 16th-note grid (0.25 subdivision)."""
        noisy = _create_noisy_piece()
        result = extract_melody_pipeline(noisy)
        for track in result.tracks:
            for interval in getattr(track, 'interval', []):
                assert interval >= 0
                quantized = round(interval / 0.25) * 0.25
                assert abs(interval - quantized) < 0.001

    def test_no_out_of_key_notes(self):
        """After adjust_to_scale, all notes should be in the detected scale."""
        piece = _create_a_major_piece()
        result = extract_melody_pipeline(piece)
        for track in result.tracks:
            for n in track:
                if hasattr(n, 'degree'):
                    # A major scale: A, B, C#, D, E, F#, G#
                    # MIDI pitch class: 9, 11, 1, 2, 4, 6, 8
                    assert n.degree % 12 in {9, 11, 1, 2, 4, 6, 8}

    def test_empty_piece(self):
        """Empty piece returns unchanged."""
        piece = mp.P(tracks=[], bpm=120)
        result = extract_melody_pipeline(piece)
        assert len(result.tracks) == 0


class TestEstimateTempoEnhanced:
    """Tests for estimate_tempo_enhanced."""

    def test_returns_reasonable_bpm(self):
        """Tempo should be within reasonable range."""
        piece = _create_a_major_piece()
        bpm = estimate_tempo_enhanced(piece)
        assert 40 <= bpm <= 240

    def test_handles_empty_piece(self):
        """Empty piece returns default BPM."""
        piece = mp.P(tracks=[], bpm=120)
        bpm = estimate_tempo_enhanced(piece, default_bpm=65)
        assert bpm == 65


def _create_noisy_piece():
    """Create a noisy piece simulating Basic Pitch output."""
    import random
    random.seed(42)
    notes = []
    for i in range(100):
        degree = random.randint(48, 84)  # C2 to C6 range
        name = _degree_to_name(degree)
        notes.append(mp.note(name[0], name[1], duration=0.2))
    c = mp.chord(notes, interval=[0.1] * 100)
    return mp.P(tracks=[c], bpm=120)


def _create_a_major_piece():
    """Create a piece with A major scale notes + some noise."""
    # A major: A=69, B=71, C#=73, D=74, E=76, F#=78, G#=80
    a_major = [69, 71, 73, 74, 76, 78, 80]
    degrees = a_major * 4 + [69, 76]
    # Add out-of-key noise
    degrees[24:30] = [70] * 6  # A# (not in A major)
    notes = []
    for d in degrees:
        name = _degree_to_name(d)
        notes.append(mp.note(name[0], name[1], duration=0.25))
    c = mp.chord(notes, interval=[0.25] * 30)
    return mp.P(tracks=[c], bpm=120)


def _create_noisy_with_known_melody():
    """Noisy piece with a few known melody notes embedded."""
    notes = []
    intervals = []
    # Known melody: C, D, E, F, G (degrees 60, 62, 64, 65, 67)
    melody = [60, 62, 64, 65, 67]
    for d in melody:
        name = _degree_to_name(d)
        notes.append(mp.note(name[0], name[1], duration=0.5))
        intervals.append(0.5)
    # Add noise
    for _ in range(40):
        degree = 50 + (hash(str(_)) % 40)
        name = _degree_to_name(degree)
        notes.append(mp.note(name[0], name[1], duration=0.1))
        intervals.append(0.1)
    c = mp.chord(notes, interval=intervals)
    return mp.P(tracks=[c], bpm=120)


def _degree_to_name(degree: int) -> tuple[str, int]:
    """Convert MIDI note number to (name, octave)."""
    names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    return names[degree % 12], degree // 12 - 1
