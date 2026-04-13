"""
Test fixtures for Music Agent Phase 1.

All test MIDI files are generated programmatically using musicpy
to ensure reproducibility and no external dependencies.
"""

import os
import tempfile

import pytest
import musicpy as mp


@pytest.fixture
def simple_melody_piece():
    """
    A simple 2-track piece: melody (right hand) + chords (left hand).
    Key: C major, 4/4, 120 BPM, 4 measures.

    Melody: C5 D5 E5 F5 | G5 F5 E5 D5 | C5 E5 G5 C6 | G5 F5 E5 D5
    Chords: C | G | Am | F
    """
    bpm = 120

    # Melody track (single notes, quarter notes, sequential timing)
    melody_notes = [
        mp.note('C', 5, duration=0.25),
        mp.note('D', 5, duration=0.25),
        mp.note('E', 5, duration=0.25),
        mp.note('F', 5, duration=0.25),
        mp.note('G', 5, duration=0.25),
        mp.note('F', 5, duration=0.25),
        mp.note('E', 5, duration=0.25),
        mp.note('D', 5, duration=0.25),
        mp.note('C', 5, duration=0.25),
        mp.note('E', 5, duration=0.25),
        mp.note('G', 5, duration=0.25),
        mp.note('C', 6, duration=0.25),
        mp.note('G', 5, duration=0.25),
        mp.note('F', 5, duration=0.25),
        mp.note('E', 5, duration=0.25),
        mp.note('D', 5, duration=0.25),
    ]
    melody = mp.chord(melody_notes, interval=[0] + [0.25] * 15)

    # Chord track: block chords, one per measure (whole notes)
    # Use | operator to concatenate with proper timing
    c_chord = mp.chord(['C3', 'E3', 'G3'], duration=1.0, interval=[0, 0, 0])
    g_chord = mp.chord(['G2', 'B2', 'D3'], duration=1.0, interval=[0, 0, 0])
    am_chord = mp.chord(['A2', 'C3', 'E3'], duration=1.0, interval=[0, 0, 0])
    f_chord = mp.chord(['F2', 'A2', 'C3'], duration=1.0, interval=[0, 0, 0])
    chords = c_chord | g_chord | am_chord | f_chord

    piece = mp.P(
        tracks=[melody, chords],
        instruments=[1, 1],
        start_times=[0, 0],
        bpm=bpm,
    )
    return piece


@pytest.fixture
def pop_song_piece():
    """
    A 3-track piece simulating a pop song:
    Track 1: Vocal melody
    Track 2: Guitar chords
    Track 3: Bass line

    Key: G major, 4/4, 100 BPM.
    """
    bpm = 100

    # Vocal melody
    vocal = mp.chord([
        mp.note('G', 4, duration=0.5),
        mp.note('A', 4, duration=0.5),
        mp.note('B', 4, duration=0.5),
        mp.note('D', 5, duration=0.5),
        mp.note('B', 4, duration=0.5),
        mp.note('A', 4, duration=0.5),
        mp.note('G', 4, duration=1.0),
    ], interval=[0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5])

    # Guitar chords (strummed, whole notes)
    g_chord = mp.chord(['G3', 'B3', 'D4'], duration=1.0, interval=[0, 0, 0])
    d_chord = mp.chord(['D3', 'F#3', 'A3'], duration=1.0, interval=[0, 0, 0])
    em_chord = mp.chord(['E3', 'G3', 'B3'], duration=1.0, interval=[0, 0, 0])
    c_chord = mp.chord(['C3', 'E3', 'G3'], duration=1.0, interval=[0, 0, 0])
    guitar = g_chord | d_chord | em_chord | c_chord

    # Bass line (quarter notes)
    bass = mp.chord([
        mp.note('G', 2, duration=0.25),
        mp.note('G', 2, duration=0.25),
        mp.note('D', 3, duration=0.25),
        mp.note('D', 3, duration=0.25),
        mp.note('E', 2, duration=0.25),
        mp.note('E', 2, duration=0.25),
        mp.note('C', 3, duration=0.25),
        mp.note('C', 3, duration=0.25),
    ], interval=[0, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25])

    piece = mp.P(
        tracks=[vocal, guitar, bass],
        instruments=[1, 25, 33],
        start_times=[0, 0, 0],
        bpm=bpm,
    )
    return piece


@pytest.fixture
def single_track_piece():
    """
    A single-track monophonic melody.
    Key: C major, simple scale.
    """
    bpm = 120
    notes = [
        mp.note('C', 4, duration=0.25),
        mp.note('D', 4, duration=0.25),
        mp.note('E', 4, duration=0.25),
        mp.note('F', 4, duration=0.25),
        mp.note('G', 4, duration=0.25),
        mp.note('A', 4, duration=0.25),
        mp.note('B', 4, duration=0.25),
        mp.note('C', 5, duration=0.25),
    ]
    melody = mp.chord(notes=notes, interval=[0] + [0.25] * (len(notes) - 1))
    piece = mp.P(
        tracks=[melody],
        instruments=[1],
        start_times=[0],
        bpm=bpm,
    )
    return piece


@pytest.fixture
def midi_dir(tmp_path):
    """
    Creates a temporary directory and writes fixture MIDI files.
    Returns (tmp_path, write_midi_function).
    """

    def write_midi(piece, name):
        path = os.path.join(str(tmp_path), name)
        mp.write(piece, name=path)
        return path

    return tmp_path, write_midi


@pytest.fixture
def multi_track_piece():
    """
    A multi-track piece simulating a real MIDI with harmony spread across tracks.
    Key: C major, 4/4, 120 BPM, 8 measures.

    Track 1: harmony (C-G-Am-F block chords, whole notes)
    Track 2: bass line (root notes, half notes)
    Track 3: effect track (very short notes, should be excluded)
    """
    bpm = 120

    # Track 1: block chords, one per measure
    harmony_notes = []
    harmony_intervals = []
    chord_data = [
        (['C3', 'E3', 'G3', 'C4', 'E4', 'G4'], 1.0),
        (['G2', 'B2', 'D3', 'G3', 'B3', 'D4'], 1.0),
        (['A2', 'C3', 'E3', 'A3', 'C4', 'E4'], 1.0),
        (['F2', 'A2', 'C3', 'F3', 'A3', 'C4'], 1.0),
        (['C3', 'E3', 'G3', 'C4', 'E4', 'G4'], 1.0),
        (['G2', 'B2', 'D3', 'G3', 'B3', 'D4'], 1.0),
        (['A2', 'C3', 'E3', 'A3', 'C4', 'E4'], 1.0),
        (['F2', 'A2', 'C3', 'F3', 'A3', 'C4'], 1.0),
    ]
    for pos, (chord_notes, dur) in enumerate(chord_data):
        for name in chord_notes:
            harmony_notes.append(mp.note(name[0], int(name[1]), duration=dur))
            harmony_intervals.append(float(pos))
    harmony = mp.chord(harmony_notes, interval=harmony_intervals)

    # Track 2: bass line (root notes, half notes, 2 per measure)
    bass_notes = []
    bass_intervals = []
    bass_pos = 0.0
    for root_note, oct in [('C', 2), ('G', 2), ('A', 2), ('F', 2),
                            ('C', 2), ('G', 2), ('A', 2), ('F', 2)]:
        bass_notes.append(mp.note(root_note, oct, duration=0.5))
        bass_intervals.append(bass_pos)
        bass_notes.append(mp.note(root_note, oct, duration=0.5))
        bass_intervals.append(bass_pos + 0.5)
        bass_pos += 1.0
    bass = mp.chord(bass_notes, interval=bass_intervals)

    # Track 3: effect track — many very-short notes (should be excluded)
    effect_notes = [mp.note('C', 1, duration=0.002) for _ in range(200)]
    effect_intervals = [float(i) * 0.002 for i in range(200)]
    effect = mp.chord(effect_notes, interval=effect_intervals)

    piece = mp.P(
        tracks=[harmony, bass, effect],
        instruments=[1, 1, 1],
        start_times=[0, 0, 0],
        bpm=bpm,
    )
    return piece


@pytest.fixture
def four_voice_piece():
    """
    A 4-track piece simulating SATB voicing in C major.
    Key: C major, 4/4, 120 BPM, 4 measures.

    Track 0 (Soprano/Melody): C5 D5 E5 F5 | G5 A5 G5 F5 | E5 D5 C5 G4 | C5 - - -
    Track 1 (Alto/Harmony):   E4 F4 G4 A4 | B4 C5 B4 A4 | G4 F4 E4 D4 | E4 - - -
    Track 2 (Tenor/Inner):    C4 D4 E4 F4 | G4 A4 G4 F4 | E4 D4 C4 B3 | C4 - - -
    Track 3 (Bass):           C2 G2 C3 G2 | C2 G2 C3 G2 | A2 E3 A3 E2 | F2 C3 F3 C2
    """
    bpm = 120

    soprano = mp.chord([
        mp.note('C', 5, duration=0.25), mp.note('D', 5, duration=0.25),
        mp.note('E', 5, duration=0.25), mp.note('F', 5, duration=0.25),
        mp.note('G', 5, duration=0.25), mp.note('A', 5, duration=0.25),
        mp.note('G', 5, duration=0.25), mp.note('F', 5, duration=0.25),
        mp.note('E', 5, duration=0.25), mp.note('D', 5, duration=0.25),
        mp.note('C', 5, duration=0.25), mp.note('G', 4, duration=0.25),
        mp.note('C', 5, duration=1.0),
    ], interval=[0, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25])

    alto = mp.chord([
        mp.note('E', 4, duration=0.25), mp.note('F', 4, duration=0.25),
        mp.note('G', 4, duration=0.25), mp.note('A', 4, duration=0.25),
        mp.note('B', 4, duration=0.25), mp.note('C', 5, duration=0.25),
        mp.note('B', 4, duration=0.25), mp.note('A', 4, duration=0.25),
        mp.note('G', 4, duration=0.25), mp.note('F', 4, duration=0.25),
        mp.note('E', 4, duration=0.25), mp.note('D', 4, duration=0.25),
        mp.note('E', 4, duration=1.0),
    ], interval=[0, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25])

    tenor = mp.chord([
        mp.note('C', 4, duration=0.25), mp.note('D', 4, duration=0.25),
        mp.note('E', 4, duration=0.25), mp.note('F', 4, duration=0.25),
        mp.note('G', 4, duration=0.25), mp.note('A', 4, duration=0.25),
        mp.note('G', 4, duration=0.25), mp.note('F', 4, duration=0.25),
        mp.note('E', 4, duration=0.25), mp.note('D', 4, duration=0.25),
        mp.note('C', 4, duration=0.25), mp.note('B', 3, duration=0.25),
        mp.note('C', 4, duration=1.0),
    ], interval=[0, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25])

    bass = mp.chord([
        mp.note('C', 2, duration=0.5), mp.note('G', 2, duration=0.5),
        mp.note('C', 3, duration=0.5), mp.note('G', 2, duration=0.5),
        mp.note('C', 2, duration=0.5), mp.note('G', 2, duration=0.5),
        mp.note('C', 3, duration=0.5), mp.note('G', 2, duration=0.5),
        mp.note('A', 2, duration=0.5), mp.note('E', 3, duration=0.5),
        mp.note('A', 3, duration=0.5), mp.note('E', 2, duration=0.5),
        mp.note('F', 2, duration=0.5), mp.note('C', 3, duration=0.5),
        mp.note('F', 3, duration=0.5), mp.note('C', 2, duration=0.5),
    ], interval=[0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5])

    return mp.P(
        tracks=[soprano, alto, tenor, bass],
        instruments=[40, 40, 41, 42],
        start_times=[0, 0, 0, 0],
        bpm=bpm,
    )


@pytest.fixture
def full_harmony_piece():
    """
    A multi-track piece with clear melody, harmony, and bass separation.
    Key: C major, 4/4, 120 BPM, 4 measures.

    Track 0: Melody (high register)
    Track 1: Harmony (mid-register block chords)
    Track 2: Counter-melody (mid-high register)
    Track 3: Bass line (low register)
    Track 4: Sparse effect (should be ignored)
    """
    bpm = 120

    melody = mp.chord([
        mp.note('G', 5, duration=0.5), mp.note('E', 5, duration=0.5),
        mp.note('C', 5, duration=0.5), mp.note('D', 5, duration=0.5),
        mp.note('E', 5, duration=0.5), mp.note('F', 5, duration=0.5),
        mp.note('G', 5, duration=1.0), mp.note('E', 5, duration=0.5),
        mp.note('D', 5, duration=0.5), mp.note('C', 5, duration=0.5),
        mp.note('G', 4, duration=0.5), mp.note('C', 5, duration=1.0),
    ], interval=[0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5])

    harmony = mp.chord([
        mp.note('C', 4, duration=1.0), mp.note('E', 4, duration=1.0), mp.note('G', 4, duration=1.0),
        mp.note('G', 3, duration=1.0), mp.note('B', 3, duration=1.0), mp.note('D', 4, duration=1.0),
        mp.note('A', 3, duration=1.0), mp.note('C', 4, duration=1.0), mp.note('E', 4, duration=1.0),
        mp.note('F', 3, duration=1.0), mp.note('A', 3, duration=1.0), mp.note('C', 4, duration=1.0),
    ], interval=[0, 0, 0, 1.0, 0, 0, 1.0, 0, 0, 1.0, 0, 0])

    counter = mp.chord([
        mp.note('E', 4, duration=0.5), mp.note('F', 4, duration=0.5),
        mp.note('G', 4, duration=0.5), mp.note('A', 4, duration=0.5),
        mp.note('G', 4, duration=0.5), mp.note('F', 4, duration=0.5),
        mp.note('E', 4, duration=1.0), mp.note('D', 4, duration=0.5),
        mp.note('C', 4, duration=0.5), mp.note('B', 3, duration=0.5),
        mp.note('C', 4, duration=0.5), mp.note('E', 4, duration=1.0),
    ], interval=[0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5])

    bass = mp.chord([
        mp.note('C', 2, duration=1.0), mp.note('G', 2, duration=1.0),
        mp.note('A', 2, duration=1.0), mp.note('F', 2, duration=1.0),
    ], interval=[0, 1.0, 1.0, 1.0])

    # Sparse effect track
    effect = mp.chord([
        mp.note('C', 6, duration=0.05) for _ in range(4)
    ], interval=[0, 1.0, 2.0, 3.0])

    return mp.P(
        tracks=[melody, harmony, counter, bass, effect],
        instruments=[1, 1, 1, 1, 1],
        start_times=[0, 0, 0, 0, 0],
        bpm=bpm,
    )
