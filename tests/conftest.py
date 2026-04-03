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

    # Melody track (single notes, quarter notes)
    melody = mp.chord([
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
    ], interval=[0] * 16)

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
    melody = mp.chord(notes=notes, interval=[0] * len(notes))
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
