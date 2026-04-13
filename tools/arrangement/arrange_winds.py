"""
Wind ensemble arrangement tool.

Arranges a piece for wind ensemble:
  Standard (7 tracks):
    Track 0: Flute (melody) — GM 74
    Track 1: Clarinet in Bb (harmony) — GM 71
    Track 2: Alto Sax in Eb (harmony) — GM 65
    Track 3: Trumpet in Bb (melody double) — GM 56
    Track 4: French Horn (inner) — GM 60
    Track 5: Trombone (bass upper) — GM 57
    Track 6: Tuba (bass) — GM 53

  Quintet (5 tracks):
    Track 0: Flute
    Track 1: Clarinet in Bb
    Track 2: Trumpet in Bb
    Track 3: French Horn
    Track 4: Trombone

Supports concert pitch notation (default) and transposed notation.
"""

import musicpy as mp

from tools.analysis.extract_melody import ExtractMelodyTool
from tools.analysis.analyze_harmony import AnalyzeHarmonyTool
from tools.analysis.voice_detection import detect_voice_roles
from tools.arrangement.transposition import (
    TRANSPOSING_OFFSETS, WIND_PROGRAMS, get_wind_programs,
    transpose_to_written, STANDARD_WINDS,
)
from tools.validation.range_check import INSTRUMENT_RANGES

QUINTET_INSTRUMENTS = ['flute', 'clarinet_bb', 'trumpet_bb', 'french_horn', 'trombone']

# Wind instrument ranges
WIND_RANGES = {
    'flute': INSTRUMENT_RANGES['flute'],
    'clarinet_bb': INSTRUMENT_RANGES['clarinet'],
    'alto_sax_eb': INSTRUMENT_RANGES['alto_sax'],
    'trumpet_bb': INSTRUMENT_RANGES['trumpet'],
    'french_horn': INSTRUMENT_RANGES['french_horn'],
    'trombone': INSTRUMENT_RANGES['trombone'],
    'tuba': INSTRUMENT_RANGES['tuba'],
}


def _clamp_to_range(notes, low, high):
    """Clamp notes to a MIDI range by octave transposition."""
    result = []
    for note in notes:
        if not hasattr(note, 'degree'):
            result.append(note)
            continue
        n = mp.note(note.name, note.num, duration=getattr(note, 'duration', 0.25))
        if hasattr(note, 'volume'):
            n.volume = note.volume
        while n.degree < low:
            n.num += 1
        while n.degree > high:
            n.num -= 1
        result.append(n)
    return result


def _get_track_notes_and_intervals(track):
    """Extract notes and intervals from a track."""
    notes = track.notes if hasattr(track, 'notes') else list(track)
    intervals = getattr(track, 'interval', None)
    return notes, intervals


def _extract_bass_from_harmony(harmony, base_octave=1):
    """Generate a bass line from chord roots."""
    if not harmony:
        return mp.chord([])
    names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    bass_notes = []
    bass_intervals = []
    for i, entry in enumerate(harmony):
        chord_str = entry.get('chord', 'Cmajor')
        root = chord_str[0].upper() if chord_str else 'C'
        if len(chord_str) > 1 and chord_str[1] in ('#', 'b'):
            root = chord_str[:2]
        root_idx = names.index(root) if root in names else 0
        midi = (base_octave + 1) * 12 + root_idx
        octave = midi // 12 - 1
        name = names[root_idx]
        note = mp.note(name, octave, duration=1.0, volume=80)
        bass_notes.append(note)
        bass_intervals.append(0.0 if i == 0 else 1.0)
    return mp.chord(bass_notes, interval=bass_intervals)


class ArrangeWindsTool:
    """Arrange a piece for wind ensemble."""

    name = "arrange_for_winds"
    description = (
        "Arrange a piece for wind ensemble (Flute, Clarinet, Saxophone, "
        "Trumpet, French Horn, Trombone, Tuba). "
        "Supports transposing instruments and concert pitch notation. "
        "Parameters: instrumentation (standard/quintet), concert_pitch_notation (bool)."
    )

    def run(self, piece, instrumentation: str = 'standard',
            concert_pitch_notation: bool = True) -> mp.P.__class__:
        """
        Arrange a piece for wind ensemble.

        Args:
            piece: A musicpy piece object.
            instrumentation: 'standard' (7 tracks) or 'quintet' (5 tracks).
            concert_pitch_notation: If True (default), keep all at concert pitch.
                If False, transpose Bb/Eb instruments to written pitch.

        Returns:
            A multi-track piece with wind instruments.
        """
        if not piece.tracks:
            return self._empty_result(piece, instrumentation)

        # Select instruments
        if instrumentation == 'quintet':
            inst_list = QUINTET_INSTRUMENTS
        else:
            inst_list = list(STANDARD_WINDS)

        # Detect voice roles
        roles = detect_voice_roles(piece)
        melody_tracks = roles.get('melody', [])
        harmony_tracks = roles.get('harmony', [])
        inner_tracks = roles.get('inner_voice', [])
        bass_tracks = roles.get('bass', [])

        n_active = len([t for t in piece.tracks if
                        hasattr(t, 'notes') and len(t.notes) > 0])

        # Collect notes
        melody_notes, melody_intervals = self._collect_notes(piece, melody_tracks)
        harmony_notes, harmony_intervals = self._collect_notes(piece, harmony_tracks)
        inner_notes, inner_intervals = self._collect_notes(piece, inner_tracks)
        bass_notes, bass_intervals = self._collect_notes(piece, bass_tracks)

        # Derive missing voices
        if n_active <= 2:
            harmony_raw = AnalyzeHarmonyTool().run(piece, granularity='measure')
            if not bass_notes:
                bass_chord = _extract_bass_from_harmony(harmony_raw, base_octave=1)
                bass_notes, bass_intervals = _get_track_notes_and_intervals(bass_chord)
            if not inner_notes:
                # Create inner voice from 3rd/5th of chords
                inner_notes, inner_intervals = self._create_inner_voice(harmony_raw)
            if not melody_notes:
                melody_notes, melody_intervals = _get_track_notes_and_intervals(
                    ExtractMelodyTool().run(piece)
                )

        # Map voices to wind sections
        track_data = {}
        for inst in inst_list:
            track_data[inst] = self._map_voice_to_instrument(
                inst, melody_notes, melody_intervals,
                harmony_notes, harmony_intervals,
                inner_notes, inner_intervals,
                bass_notes, bass_intervals,
            )

        # Apply transposition if not in concert pitch mode
        for inst in inst_list:
            notes, intervals = track_data[inst]
            if not concert_pitch_notation and any(
                inst in key for key in TRANSPOSING_OFFSETS if TRANSPOSING_OFFSETS[key] != 0
            ):
                if inst in ['clarinet_bb', 'trumpet_bb', 'alto_sax_eb',
                            'tenor_sax_eb', 'baritone_sax_eb', 'french_horn_f']:
                    notes = transpose_to_written(notes, inst)
                # Map generic names
                elif inst == 'clarinet' or inst == 'clarinet_bb':
                    notes = transpose_to_written(notes, 'clarinet_bb')
                elif inst == 'trumpet' or inst == 'trumpet_bb':
                    notes = transpose_to_written(notes, 'trumpet_bb')
                elif inst == 'alto_sax' or inst == 'alto_sax_eb':
                    notes = transpose_to_written(notes, 'alto_sax_eb')
            track_data[inst] = (notes, intervals)

        # Clamp to instrument ranges and build tracks
        tracks = []
        programs = []
        for inst in inst_list:
            notes, intervals = track_data[inst]
            low, high = WIND_RANGES.get(inst, (21, 108))
            clamped = _clamp_to_range(notes, low, high) if notes else []
            tracks.append(mp.chord(clamped, interval=intervals or [0]) if clamped else mp.chord([]))
            programs.append(WIND_PROGRAMS.get(inst, 0))

        result = mp.P(
            tracks=tracks,
            instruments=programs,
            start_times=[0] * len(tracks),
            bpm=piece.bpm if piece.bpm else 120,
        )
        return result

    def _empty_result(self, piece, instrumentation):
        """Return empty wind ensemble piece."""
        if instrumentation == 'quintet':
            inst_list = QUINTET_INSTRUMENTS
        else:
            inst_list = list(STANDARD_WINDS)
        programs = [WIND_PROGRAMS.get(i, 0) for i in inst_list]
        return mp.P(
            tracks=[mp.chord([])] * len(inst_list),
            instruments=programs,
            start_times=[0] * len(inst_list),
            bpm=piece.bpm if piece.bpm else 120,
        )

    def _collect_notes(self, piece, track_indices):
        """Collect notes from specified tracks."""
        if not track_indices:
            return [], None
        notes = []
        intervals = []
        for idx in track_indices:
            if idx < len(piece.tracks):
                track = piece.tracks[idx]
                n, iv = _get_track_notes_and_intervals(track)
                notes.extend(n)
                if intervals:
                    intervals.extend(iv if iv else [0.25] * len(n))
                else:
                    intervals = list(iv) if iv else [0.25] * len(n)
        return notes, intervals

    def _map_voice_to_instrument(self, inst, melody_notes, melody_intervals,
                                  harmony_notes, harmony_intervals,
                                  inner_notes, inner_intervals,
                                  bass_notes, bass_intervals):
        """Map the appropriate voice to a wind instrument."""
        if inst in ('flute', 'trumpet_bb'):
            # Melody instruments
            return melody_notes or [], melody_intervals or [0]
        elif inst in ('clarinet_bb', 'alto_sax_eb'):
            # Harmony instruments
            return harmony_notes or [], harmony_intervals or [0]
        elif inst == 'french_horn':
            # Inner voice
            return inner_notes or [], inner_intervals or [0]
        elif inst == 'trombone':
            # Upper bass
            return bass_notes or [], bass_intervals or [0]
        elif inst == 'tuba':
            # Low bass — transpose down octave if using same bass data
            if bass_notes:
                lowered = []
                for n in bass_notes:
                    if hasattr(n, 'degree'):
                        oct_shifted = mp.note(n.name, n.num - 1,
                                              duration=getattr(n, 'duration', 0.25))
                        if hasattr(n, 'volume'):
                            oct_shifted.volume = n.volume
                        lowered.append(oct_shifted)
                    else:
                        lowered.append(n)
                return lowered, bass_intervals
            return [], []
        return [], []

    def _create_inner_voice(self, harmony):
        """Create inner voice from chord 3rds in middle register."""
        if not harmony:
            return [], None
        names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        inner_notes = []
        inner_intervals = []
        for i, entry in enumerate(harmony):
            chord_str = entry.get('chord', 'Cmajor')
            root = chord_str[0].upper() if chord_str else 'C'
            root_idx = names.index(root) if root in names else 0
            third_idx = (root_idx + 4) % 12  # Major 3rd
            midi = 4 * 12 + third_idx
            octave = midi // 12 - 1
            name = names[third_idx]
            note = mp.note(name, octave, duration=1.0, volume=70)
            inner_notes.append(note)
            inner_intervals.append(0.0 if i == 0 else 1.0)
        return inner_notes, inner_intervals
