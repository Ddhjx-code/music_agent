"""Skeleton test to verify pytest and musicpy are working."""

import musicpy as mp


def test_musicpy_import():
    """Verify musicpy is installed and functional."""
    note = mp.note('C', 5)
    assert note.degree == 72
    assert str(note) == 'C5'


def test_musicpy_chord():
    """Verify chord creation."""
    c = mp.chord(['C4', 'E4', 'G4'])
    assert len(c) == 3


def test_musicpy_piece():
    """Verify piece creation and round-trip."""
    melody = mp.chord([
        mp.note('C', 4, duration=0.25),
        mp.note('D', 4, duration=0.25),
    ], interval=[0, 0])
    piece = mp.P(
        tracks=[melody],
        instruments=[1],
        start_times=[0],
        bpm=120,
    )
    assert len(piece.tracks) == 1
    assert piece.bpm == 120
