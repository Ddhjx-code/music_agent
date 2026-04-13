"""
String quartet arrangement tool.

Arranges a piece for string quartet:
  Track 0: Violin 1 (melody) — GM 40, range G3-A7
  Track 1: Violin 2 (harmony) — GM 40, range G3-A7
  Track 2: Viola (inner voice) — GM 41, range C3-E6
  Track 3: Cello (bass) — GM 42, range C2-A5

Handles input from 1 to 4+ tracks:
- 1 track: extracts melody, derives harmony/bass from analysis
- 2 tracks: melody + harmony → derive inner/bass
- 3 tracks: melody + harmony + bass → derive inner
- 4+ tracks: map to SATB roles
"""

import musicpy as mp

from tools.analysis.extract_melody import ExtractMelodyTool
from tools.analysis.analyze_harmony import AnalyzeHarmonyTool
from tools.harmony.generate_accompaniment import GenerateAccompanimentTool
from tools.analysis.voice_detection import detect_voice_roles
from tools.validation.range_check import INSTRUMENT_RANGES

# String quartet GM programs
STRINGS_QUARTET_PROGRAMS = [40, 40, 41, 42]  # Violin, Violin, Viola, Cello

# Per-instrument ranges
STRING_RANGES = {
    'violin1': INSTRUMENT_RANGES['violin'],     # 67-115
    'violin2': INSTRUMENT_RANGES['violin'],     # 67-115
    'viola': INSTRUMENT_RANGES['viola'],         # 48-93
    'cello': INSTRUMENT_RANGES['cello'],         # 36-88
}


def _clamp_to_range(notes, low, high):
    """Clamp notes to a MIDI range by octave transposition."""
    result = []
    for note in notes:
        if not hasattr(note, 'degree'):
            result.append(note)
            continue
        deg = note.degree
        n = mp.note(note.name, note.num, duration=getattr(note, 'duration', 0.25))
        if hasattr(note, 'volume'):
            n.volume = note.volume
        while n.degree < low:
            n.num += 1
        while n.degree > high:
            n.num -= 1
        result.append(n)
    return result


def _extract_bass_from_harmony(harmony, base_octave=2):
    """Generate a bass line from chord roots."""
    if not harmony:
        return mp.chord([])

    names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    bass_notes = []
    bass_intervals = []

    for i, entry in enumerate(harmony):
        chord_str = entry.get('chord', 'Cmajor')
        # Extract root from chord name
        root = chord_str[0].upper() if chord_str else 'C'
        if len(chord_str) > 1 and chord_str[1] in ('#', 'b'):
            root = chord_str[:2]

        root_idx = names.index(root) if root in names else 0
        midi = (base_octave + 1) * 12 + root_idx
        octave = midi // 12 - 1
        name = names[root_idx]

        note = mp.note(name, octave, duration=1.0, volume=80)
        bass_notes.append(note)
        if i == 0:
            bass_intervals.append(0.0)
        else:
            bass_intervals.append(1.0)

    return mp.chord(bass_notes, interval=bass_intervals)


def _get_track_notes_and_intervals(track):
    """Extract notes and intervals from a track."""
    notes = track.notes if hasattr(track, 'notes') else list(track)
    intervals = getattr(track, 'interval', None)
    return notes, intervals


class ArrangeStringsTool:
    """Arrange a piece for string quartet."""

    name = "arrange_for_strings"
    description = (
        "Arrange a piece for string quartet (Violin 1, Violin 2, Viola, Cello). "
        "Maps melody to Vln1, harmony to Vln2, inner voice to Viola, bass to Cello. "
        "Automatically checks instrument ranges and voice leading."
    )

    def run(self, piece, voicing: str = 'standard',
            check_voice_leading: bool = True) -> mp.P.__class__:
        """
        Arrange a piece for string quartet.

        Args:
            piece: A musicpy piece object.
            voicing: 'standard' (default). Reserved for future voicing options.
            check_voice_leading: If True, check and report voice leading issues.

        Returns:
            A 4-track piece: Vln1, Vln2, Vla, Vcl.
        """
        if not piece.tracks:
            return self._empty_result(piece)

        # Detect voice roles
        roles = detect_voice_roles(piece)
        melody_tracks = roles.get('melody', [])
        harmony_tracks = roles.get('harmony', [])
        inner_tracks = roles.get('inner_voice', [])
        bass_tracks = roles.get('bass', [])

        n_active = len([t for t in piece.tracks if
                        hasattr(t, 'notes') and len(t.notes) > 0])

        # Extract note data for each role
        melody_notes, melody_intervals = self._collect_notes(piece, melody_tracks)
        harmony_notes, harmony_intervals = self._collect_notes(piece, harmony_tracks)
        inner_notes, inner_intervals = self._collect_notes(piece, inner_tracks)
        bass_notes, bass_intervals = self._collect_notes(piece, bass_tracks)

        # Handle insufficient voices
        if n_active == 1:
            # Derive 4 voices from melody + harmony analysis
            harmony_raw = AnalyzeHarmonyTool().run(piece, granularity='measure')
            if not melody_notes:
                melody_notes, melody_intervals = _get_track_notes_and_intervals(
                    ExtractMelodyTool().run(piece)
                )
            if not harmony_notes:
                # Create harmony by harmonizing melody at 3rd below
                harmony_notes, harmony_intervals = self._harmonize_at_third(
                    melody_notes, melody_intervals
                )
            if not bass_notes:
                bass_notes_chord = _extract_bass_from_harmony(harmony_raw, base_octave=2)
                bass_notes, bass_intervals = _get_track_notes_and_intervals(bass_notes_chord)
            if not inner_notes:
                # Create inner voice from chord tones
                inner_notes, inner_intervals = self._create_inner_voice(
                    harmony_raw, melody_notes
                )

        elif n_active == 2:
            # Melody + harmony → derive inner + bass
            harmony_raw = AnalyzeHarmonyTool().run(piece, granularity='measure')
            if not bass_notes:
                bass_chord = _extract_bass_from_harmony(harmony_raw, base_octave=2)
                bass_notes, bass_intervals = _get_track_notes_and_intervals(bass_chord)
            if not inner_notes:
                inner_notes, inner_intervals = self._create_inner_voice(
                    harmony_raw, melody_notes
                )

        elif n_active == 3:
            # Melody + harmony + bass → derive inner
            harmony_raw = AnalyzeHarmonyTool().run(piece, granularity='measure')
            if not inner_notes:
                inner_notes, inner_intervals = self._create_inner_voice(
                    harmony_raw, melody_notes
                )

        # Clamp to instrument ranges
        vln1_notes = _clamp_to_range(melody_notes or [], *STRING_RANGES['violin1'])
        vln2_notes = _clamp_to_range(harmony_notes or [], *STRING_RANGES['violin2'])
        vla_notes = _clamp_to_range(inner_notes or [], *STRING_RANGES['viola'])
        vcl_notes = _clamp_to_range(bass_notes or [], *STRING_RANGES['cello'])

        # Build tracks
        vln1 = mp.chord(vln1_notes, interval=melody_intervals or [0]) if vln1_notes else mp.chord([])
        vln2 = mp.chord(vln2_notes, interval=harmony_intervals or [0]) if vln2_notes else mp.chord([])
        vla = mp.chord(vla_notes, interval=inner_intervals or [0]) if vla_notes else mp.chord([])
        vcl = mp.chord(vcl_notes, interval=bass_intervals or [0]) if vcl_notes else mp.chord([])

        result = mp.P(
            tracks=[vln1, vln2, vla, vcl],
            instruments=STRINGS_QUARTET_PROGRAMS,
            start_times=[0, 0, 0, 0],
            bpm=piece.bpm if piece.bpm else 120,
        )

        # Voice leading check (informational only)
        if check_voice_leading and result.tracks:
            issues = self._check_voice_leading(result)
            if issues:
                # Log but don't block
                print(f"  Voice leading warnings: {len(issues)} issue(s)")

        return result

    def _empty_result(self, piece):
        """Return empty 4-track piece."""
        return mp.P(
            tracks=[mp.chord([])] * 4,
            instruments=STRINGS_QUARTET_PROGRAMS,
            start_times=[0, 0, 0, 0],
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

    def _harmonize_at_third(self, melody_notes, melody_intervals):
        """Create harmony by harmonizing melody at a 3rd below."""
        if not melody_notes:
            return [], None
        harmony_notes = []
        for n in melody_notes:
            if hasattr(n, 'degree'):
                new_degree = n.degree - 4  # Major 3rd below
                names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
                octave = new_degree // 12 - 1
                name = names[new_degree % 12]
                h = mp.note(name, octave, duration=getattr(n, 'duration', 0.25))
                if hasattr(n, 'volume'):
                    h.volume = max(50, n.volume - 10) if n.volume else 75
                harmony_notes.append(h)
            else:
                harmony_notes.append(n)
        return harmony_notes, melody_intervals

    def _create_inner_voice(self, harmony, melody_notes):
        """Create inner voice from chord roots/5ths in middle register."""
        if not harmony:
            return [], None
        names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        inner_notes = []
        inner_intervals = []
        for i, entry in enumerate(harmony):
            chord_str = entry.get('chord', 'Cmajor')
            # Use 5th of chord for inner voice
            root = chord_str[0].upper() if chord_str else 'C'
            root_idx = names.index(root) if root in names else 0
            fifth_idx = (root_idx + 7) % 12  # Perfect 5th
            midi = 4 * 12 + fifth_idx  # Octave 4
            octave = midi // 12 - 1
            name = names[fifth_idx]
            note = mp.note(name, octave, duration=1.0, volume=70)
            inner_notes.append(note)
            inner_intervals.append(0.0 if i == 0 else 1.0)
        return inner_notes, inner_intervals

    def _check_voice_leading(self, piece):
        """Check for parallel perfect fifths and octaves between adjacent voices."""
        issues = []
        if len(piece.tracks) < 2:
            return issues

        for i in range(len(piece.tracks) - 1):
            notes_a = [n for n in piece.tracks[i] if hasattr(n, 'degree')]
            notes_b = [n for n in piece.tracks[i + 1] if hasattr(n, 'degree')]
            if not notes_a or not notes_b:
                continue

            # Compare consecutive note pairs
            min_len = min(len(notes_a), len(notes_b))
            prev_interval = None
            for j in range(min_len):
                interval = notes_a[j].degree - notes_b[j].degree
                if prev_interval is not None:
                    # Check for parallel perfect intervals
                    if abs(prev_interval) == 7 and abs(interval) == 7:
                        issues.append(f"Parallel 5th between voices {i}/{i+1} at position {j}")
                    elif abs(prev_interval) == 12 and abs(interval) == 12:
                        issues.append(f"Parallel octave between voices {i}/{i+1} at position {j}")
                    elif abs(prev_interval) == 19 and abs(interval) == 19:
                        issues.append(f"Parallel compound interval between voices {i}/{i+1} at position {j}")
                prev_interval = interval

        return issues
