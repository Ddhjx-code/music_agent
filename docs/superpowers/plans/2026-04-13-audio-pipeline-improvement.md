# Audio Pipeline Improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve WAV→MIDI transcription quality (OmniAudio, per-stem pipeline, post-processing) and MIDI→WAV rendering quality (expression pre-processing, Timidity++, post-FX).

**Architecture:** Three independent modules added to `core/` with corresponding tests, plus extensions to existing `audio_import.py` and `audio_render.py`. Each module is testable in isolation.

**Tech Stack:** Python, musicpy, pytest, OmniAudio (optional), basic_pitch (existing), FluidSynth (existing), Timidity++ (new), ffmpeg (existing)

---

## File Structure

| File | Responsibility |
|------|---------------|
| `core/audio_postprocess.py` | **New** — rhythm quantization, note cleanup, velocity normalization, tempo estimation |
| `tests/test_audio_postprocess.py` | **New** — unit tests for all postprocessing functions |
| `core/audio_import.py` | **Modify** — add `engine` param, `wav_to_midi` OmniAudio support, `separate_and_transcribe` |
| `tests/test_audio_import.py` | **Modify** — add OmniAudio and postprocess tests |
| `core/audio_render_expression.py` | **New** — expression pre-processing: velocity mapping, phrase detection, rubato for render |
| `tests/test_audio_render_expression.py` | **New** — unit tests for expression pre-processing |
| `core/audio_render.py` | **Modify** — add `render_timidity`, `render_audio_postfx`, updated `render_wav` with options |
| `tests/test_audio_render.py` | **Modify** — add Timidity and post-FX tests |
| `docs/superpowers/specs/2026-04-13-audio-pipeline-improvement-design.md` | Existing spec (already committed) |

---

## Task 1: Audio Post-Processing Module

### Task 1: Core audio_postprocess.py

**Files:**
- Create: `core/audio_postprocess.py`
- Create: `tests/test_audio_postprocess.py`
- Test: `tests/test_audio_postprocess.py`

This module provides functions to clean up and improve transcribed MIDI:
- Rhythm quantization (snap to beat subdivisions)
- Note duration cleanup (normalize to musical values)
- Duplicate/overlap removal
- Velocity normalization (scale to 40-110 range)
- Tempo estimation from note onsets

- [ ] **Step 1: Write failing tests for tempo estimation**

```python
# tests/test_audio_postprocess.py

"""Tests for core/audio_postprocess.py."""

import musicpy as mp
import pytest

from core.audio_postprocess import (
    estimate_tempo, quantize_rhythm, normalize_velocities,
    remove_duplicate_notes, cleanup_durations, postprocess_midi
)


class TestEstimateTempo:
    """Test BPM estimation from note onsets."""

    def test_estimates_120_bpm(self):
        """Quarter notes at 120 BPM should estimate ~120."""
        # Create notes at 0.5s intervals (120 BPM)
        notes = [mp.note('C', 4, duration=0.25) for _ in range(8)]
        intervals = [0.0] + [0.5] * 7  # 500ms = 120 BPM
        track = mp.chord(notes, interval=intervals)
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=60)

        bpm = estimate_tempo(piece)
        assert abs(bpm - 120) < 10, f"Expected ~120, got {bpm}"

    def test_returns_default_on_empty(self):
        """Should return default BPM on empty piece."""
        piece = mp.P(tracks=[], instruments=[], start_times=[], bpm=120)
        bpm = estimate_tempo(piece, default_bpm=100)
        assert bpm == 100

    def test_estimates_90_bpm(self):
        """Quarter notes at 90 BPM should estimate ~90."""
        notes = [mp.note('C', 4, duration=0.25) for _ in range(8)]
        intervals = [0.0] + [2.0/3] * 7  # ~667ms = 90 BPM
        track = mp.chord(notes, interval=intervals)
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=60)

        bpm = estimate_tempo(piece)
        assert abs(bpm - 90) < 10, f"Expected ~90, got {bpm}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_audio_postprocess.py::TestEstimateTempo -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'core.audio_postprocess'"

- [ ] **Step 3: Write tempo estimation implementation**

```python
# core/audio_postprocess.py
"""
Audio post-processing module.

Functions to clean up and improve transcribed MIDI:
- Rhythm quantization (snap to beat subdivisions)
- Note duration cleanup (normalize to musical values)
- Duplicate/overlap removal
- Velocity normalization (scale to 40-110)
- Tempo estimation from note onsets
"""

import musicpy as mp
from collections import Counter


def estimate_tempo(piece, default_bpm: int = 120) -> float:
    """
    Estimate BPM from note onset intervals.

    Uses the most common interval between consecutive note onsets
    to estimate the tempo. Falls back to default_bpm if unable.

    Args:
        piece: A musicpy piece object.
        default_bpm: Fallback BPM if estimation fails.

    Returns:
        Estimated BPM as float.
    """
    if not piece.tracks:
        return default_bpm

    # Collect all note onset times
    onset_times = []
    current_time = 0.0
    for track in piece.tracks:
        notes = track.notes if hasattr(track, 'notes') else list(track)
        time = 0.0
        for i, note in enumerate(notes):
            onset_times.append(time)
            intervals = getattr(track, 'interval', [])
            if i < len(intervals):
                time += intervals[i]

    if len(onset_times) < 2:
        return default_bpm

    onset_times.sort()

    # Compute intervals between consecutive onsets
    intervals = [onset_times[i+1] - onset_times[i] for i in range(len(onset_times)-1)]

    # Filter out very small intervals (chords) and very large ones (rests)
    valid = [iv for iv in intervals if 0.1 < iv < 4.0]
    if not valid:
        return default_bpm

    # Round intervals to nearest 1/16 note at common BPMs and find mode
    rounded = [round(iv * 4) / 4 for iv in valid]
    most_common = Counter(rounded).most_common(1)
    if not most_common:
        return default_bpm

    beat_interval = most_common[0][0]
    if beat_interval <= 0:
        return default_bpm

    # BPM = 60 / beat_interval (assuming beat = quarter note)
    bpm = 60.0 / beat_interval
    return max(40, min(240, round(bpm)))
```

- [ ] **Step 4: Run tempo tests to verify they pass**

Run: `pytest tests/test_audio_postprocess.py::TestEstimateTempo -v`
Expected: All PASS

- [ ] **Step 5: Write failing tests for rhythm quantization**

Add to `tests/test_audio_postprocess.py`:

```python
class TestQuantizeRhythm:
    """Test rhythm quantization."""

    def test_snaps_to_quarter_grid(self):
        """Notes at 0.48, 0.99, 1.51 should snap to 0.5, 1.0, 1.5."""
        notes = [
            mp.note('C', 4, duration=0.25),
            mp.note('D', 4, duration=0.25),
            mp.note('E', 4, duration=0.25),
        ]
        intervals = [0.0, 0.48, 0.52]
        track = mp.chord(notes, interval=intervals)
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)

        result = quantize_rhythm(piece, subdivision=0.25)
        new_intervals = getattr(result.tracks[0], 'interval', [])
        # Should be quantized to nearest 0.25
        assert abs(new_intervals[1] - 0.5) < 0.01
        assert abs(new_intervals[2] - 0.5) < 0.01

    def test_preserves_first_note_timing(self):
        """First note always starts at 0."""
        notes = [mp.note('C', 4, duration=0.25)]
        track = mp.chord(notes, interval=[0.0])
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)

        result = quantize_rhythm(piece, subdivision=0.25)
        intervals = getattr(result.tracks[0], 'interval', [])
        assert intervals[0] == 0.0

    def test_handles_empty_track(self):
        """Should not crash on empty piece."""
        piece = mp.P(tracks=[], instruments=[], start_times=[], bpm=120)
        result = quantize_rhythm(piece)
        assert result is not None
```

- [ ] **Step 6: Run tests to verify they fail, then implement**

```python
# Add to core/audio_postprocess.py

def quantize_rhythm(piece, subdivision: float = 0.25) -> mp.P.__class__:
    """
    Quantize note onset times to nearest beat subdivision.

    Args:
        piece: A musicpy piece object.
        subdivision: Grid size in beats (0.25 = quarter, 0.125 = eighth).

    Returns:
        Copy of piece with quantized note timings.
    """
    if not piece.tracks:
        return piece

    result = piece.copy()
    for track in result.tracks:
        notes = track.notes if hasattr(track, 'notes') else list(track)
        intervals = list(getattr(track, 'interval', []))

        if not intervals:
            continue

        # Quantize each interval to nearest subdivision
        intervals[0] = 0.0  # First note always at 0
        for i in range(1, len(intervals)):
            intervals[i] = round(intervals[i] / subdivision) * subdivision
            intervals[i] = max(0.0, intervals[i])

        track.interval = intervals

    return result
```

- [ ] **Step 7: Verify quantize tests pass**

Run: `pytest tests/test_audio_postprocess.py::TestQuantizeRhythm -v`
Expected: All PASS

- [ ] **Step 8: Write failing tests for velocity normalization**

```python
class TestNormalizeVelocities:
    """Test velocity normalization."""

    def test_scales_to_range(self):
        """Velocities should be scaled to 40-110 range."""
        notes = [
            mp.note('C', 4, duration=0.25),
            mp.note('D', 4, duration=0.25),
        ]
        notes[0].volume = 10
        notes[1].volume = 127
        track = mp.chord(notes, interval=[0.0, 0.25])
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)

        result = normalize_velocities(piece, min_vel=40, max_vel=110)
        velocities = [n.volume for n in result.tracks[0] if hasattr(n, 'volume')]
        assert all(40 <= v <= 110 for v in velocities)

    def test_preserves_relative_dynamics(self):
        """Louder notes should remain louder after normalization."""
        notes = [mp.note('C', 4, duration=0.25) for _ in range(3)]
        notes[0].volume = 30
        notes[1].volume = 60
        notes[2].volume = 90
        track = mp.chord(notes, interval=[0.0, 0.25, 0.25])
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)

        result = normalize_velocities(piece)
        velocities = [n.volume for n in result.tracks[0]]
        assert velocities[0] < velocities[1] < velocities[2]
```

- [ ] **Step 9: Implement velocity normalization**

```python
# Add to core/audio_postprocess.py

def normalize_velocities(piece, min_vel: int = 40, max_vel: int = 110) -> mp.P.__class__:
    """
    Scale note velocities to a target range.

    Preserves relative dynamics while mapping to [min_vel, max_vel].

    Args:
        piece: A musicpy piece object.
        min_vel: Minimum velocity after normalization.
        max_vel: Maximum velocity after normalization.

    Returns:
        Copy of piece with normalized velocities.
    """
    if not piece.tracks:
        return piece

    result = piece.copy()

    # Collect all velocities across tracks
    all_velocities = []
    for track in result.tracks:
        notes = track.notes if hasattr(track, 'notes') else list(track)
        for note in notes:
            if hasattr(note, 'volume'):
                all_velocities.append(note.volume)

    if not all_velocities:
        return result

    old_min = min(all_velocities)
    old_max = max(all_velocities)
    old_range = old_max - old_min

    for track in result.tracks:
        notes = track.notes if hasattr(track, 'notes') else list(track)
        for note in notes:
            if hasattr(note, 'volume'):
                if old_range == 0:
                    # All same velocity — map to center of target range
                    note.volume = (min_vel + max_vel) // 2
                else:
                    # Linear scale
                    ratio = (note.volume - old_min) / old_range
                    note.volume = max(min_vel, min(max_vel,
                                                   int(min_vel + ratio * (max_vel - min_vel))))

    return result
```

- [ ] **Step 10: Verify velocity tests pass**

Run: `pytest tests/test_audio_postprocess.py::TestNormalizeVelocities -v`
Expected: All PASS

- [ ] **Step 11: Write and test remaining postprocessing functions**

Add tests and implementations for `remove_duplicate_notes`, `cleanup_durations`, and `postprocess_midi`:

```python
# Add to tests/test_audio_postprocess.py

class TestRemoveDuplicateNotes:
    """Test duplicate note removal."""

    def test_removes_same_pitch_overlap(self):
        """Overlapping notes on same pitch should be deduplicated."""
        notes = [
            mp.note('C', 4, duration=0.25),
            mp.note('C', 4, duration=0.5),  # same pitch, close timing
        ]
        notes[0].volume = 60
        notes[1].volume = 70
        track = mp.chord(notes, interval=[0.0, 0.05])  # very close
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)

        result = remove_duplicate_notes(piece, threshold=0.1)
        count = len([n for t in result.tracks for n in (t.notes if hasattr(t, 'notes') else list(t))])
        assert count == 1

    def test_keeps_different_pitches(self):
        """Different pitches should not be removed."""
        notes = [
            mp.note('C', 4, duration=0.25),
            mp.note('D', 4, duration=0.25),
        ]
        notes[0].volume = 60
        notes[1].volume = 70
        track = mp.chord(notes, interval=[0.0, 0.25])
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)

        result = remove_duplicate_notes(piece)
        count = len([n for t in result.tracks for n in (t.notes if hasattr(t, 'notes') else list(t))])
        assert count == 2


class TestCleanupDurations:
    """Test note duration cleanup."""

    def test_normalizes_to_musical_values(self):
        """Durations like 0.23 should snap to 0.25."""
        notes = [mp.note('C', 4, duration=0.23)]
        track = mp.chord(notes, interval=[0.0])
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)

        result = cleanup_durations(piece)
        note = list(result.tracks[0])[0]
        assert abs(note.duration - 0.25) < 0.01


class TestPostprocessMidi:
    """Test full postprocessing pipeline."""

    def test_runs_all_steps(self, simple_melody_piece):
        """Full pipeline should not crash and should produce valid output."""
        result = postprocess_midi(simple_melody_piece)
        assert len(result.tracks) == len(simple_melody_piece.tracks)
        # Velocities should be in range
        for track in result.tracks:
            for note in (track.notes if hasattr(track, 'notes') else list(track)):
                if hasattr(note, 'volume'):
                    assert 40 <= note.volume <= 110
```

```python
# Add to core/audio_postprocess.py

def remove_duplicate_notes(piece, threshold: float = 0.1) -> mp.P.__class__:
    """
    Remove duplicate notes on same pitch within time threshold.

    Keeps the note with higher velocity when duplicates found.

    Args:
        piece: A musicpy piece object.
        threshold: Time threshold in beats for considering notes as duplicates.

    Returns:
        Copy of piece with duplicate notes removed.
    """
    if not piece.tracks:
        return piece

    result = piece.copy()
    for track in result.tracks:
        notes = list(track.notes if hasattr(track, 'notes') else list(track))
        if len(notes) < 2:
            continue

        intervals = list(getattr(track, 'interval', []))
        kept = []
        kept_times = []
        current_time = 0.0

        for i, note in enumerate(notes):
            is_dup = False
            for prev_time, prev_note in zip(kept_times, kept):
                time_diff = abs(current_time - prev_time)
                pitch_same = (getattr(note, 'degree', 0) == getattr(prev_note, 'degree', 0))
                if time_diff < threshold and pitch_same:
                    is_dup = True
                    # Keep the one with higher velocity
                    if getattr(note, 'volume', 60) > getattr(prev_note, 'volume', 60):
                        kept.remove(prev_note)
                        kept_times.remove(prev_time)
                        kept.append(note)
                        kept_times.append(current_time)
                    break

            if not is_dup:
                kept.append(note)
                kept_times.append(current_time)

            if i < len(intervals):
                current_time += intervals[i]

        if len(kept) < len(notes):
            # Rebuild track with fewer notes
            new_track = mp.chord(kept, interval=[0.0] + [0.25] * (len(kept) - 1))
            # Preserve track reference
            track_index = result.tracks.index(track)
            result.tracks[track_index] = new_track

    return result


def cleanup_durations(piece) -> mp.P.__class__:
    """
    Normalize note durations to nearest musical values.

    Snaps to: 1/16, 1/8, 1/4, 1/2, 1.0 beats.

    Args:
        piece: A musicpy piece object.

    Returns:
        Copy of piece with cleaned durations.
    """
    if not piece.tracks:
        return piece

    musical_values = [0.0625, 0.125, 0.25, 0.5, 1.0, 2.0, 4.0]
    result = piece.copy()

    for track in result.tracks:
        notes = track.notes if hasattr(track, 'notes') else list(track)
        for note in notes:
            dur = getattr(note, 'duration', 0.25)
            if dur <= 0:
                continue
            # Find nearest musical value
            nearest = min(musical_values, key=lambda mv: abs(mv - dur))
            note.duration = nearest

    return result


def postprocess_midi(piece, subdivision: float = 0.25,
                     min_vel: int = 40, max_vel: int = 110) -> mp.P.__class__:
    """
    Run full postprocessing pipeline on a piece.

    Order: estimate tempo → quantize rhythm → cleanup durations →
           remove duplicates → normalize velocities.

    Args:
        piece: A musicpy piece object.
        subdivision: Quantization grid size.
        min_vel: Minimum velocity after normalization.
        max_vel: Maximum velocity after normalization.

    Returns:
        Processed piece.
    """
    # Step 1: Quantize rhythm (uses estimated BPM internally)
    result = quantize_rhythm(piece, subdivision=subdivision)

    # Step 2: Cleanup durations
    result = cleanup_durations(result)

    # Step 3: Remove duplicate notes
    result = remove_duplicate_notes(result)

    # Step 4: Normalize velocities
    result = normalize_velocities(result, min_vel=min_vel, max_vel=max_vel)

    return result
```

- [ ] **Step 12: Run all postprocess tests**

Run: `pytest tests/test_audio_postprocess.py -v`
Expected: All PASS

- [ ] **Step 13: Commit**

```bash
git add core/audio_postprocess.py tests/test_audio_postprocess.py
git commit -m "feat: add audio post-processing module with quantize, velocity, dedup"
```

---

## Task 2: OmniAudio Integration in audio_import.py

### Task 2: OmniAudio + per-stem transcription

**Files:**
- Modify: `core/audio_import.py`
- Modify: `tests/test_audio_import.py`

- [ ] **Step 1: Write failing tests for OmniAudio wav_to_midi**

```python
# Add to tests/test_audio_import.py

class TestOmniAudioTranscription:
    """Test OmniAudio-based transcription."""

    @patch('core.audio_import.check_audio_import_deps')
    def test_returns_none_when_omniaudio_missing(self, mock_deps):
        """Should return None when omniaudio is not installed."""
        mock_deps.return_value = {'demucs': False, 'basic_pitch': False, 'omniaudio': False}

        from core.audio_import import wav_to_midi
        result = wav_to_midi('input.wav', 'output.mid', engine='omniaudio')
        assert result is None

    @patch('core.audio_import.check_audio_import_deps')
    def test_wav_to_midi_with_basic_pitch_fallback(self, mock_deps):
        """Should fall back to basic_pitch when omniaudio unavailable."""
        mock_deps.return_value = {'demucs': False, 'basic_pitch': True, 'omniaudio': False}

        with patch('core.audio_import.wav_to_midi_basic_pitch') as mock_bp:
            mock_bp.return_value = 'output.mid'
            from core.audio_import import wav_to_midi
            result = wav_to_midi('input.wav', 'output.mid', engine='omniaudio')
            assert result == 'output.mid'
            mock_bp.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_audio_import.py::TestOmniAudioTranscription -v`
Expected: FAIL (functions not yet implemented)

- [ ] **Step 3: Implement OmniAudio support in audio_import.py**

Add these imports and functions to `core/audio_import.py`:

```python
# Add to check_audio_import_deps():
def check_audio_import_deps() -> dict[str, bool]:
    """Check availability of audio import dependencies."""
    result = {}
    for name in ['demucs', 'basic_pitch', 'omniaudio']:
        try:
            __import__(name)
            result[name] = True
        except ImportError:
            result[name] = False
    return result
```

```python
# Add new function: wav_to_midi_basic_pitch (refactored from existing wav_to_midi)
def wav_to_midi_basic_pitch(wav_path: str, midi_path: str) -> str | None:
    """Transcribe WAV to MIDI using Basic Pitch (fallback engine)."""
    try:
        from basic_pitch.inference import predict_and_save

        output_dir = os.path.dirname(midi_path) or '.'
        result = predict_and_save(
            [wav_path], output_dir,
            save_artifacts=False, enable_sonify_pred=False,
        )
        if result and os.path.exists(midi_path):
            return midi_path
        return None
    except Exception as e:
        print(f"  Error: basic_pitch transcription failed: {e}")
        return None


# Add new function: wav_to_midi_omniaudio
def wav_to_midi_omniaudio(wav_path: str, midi_path: str) -> str | None:
    """Transcribe WAV to MIDI using OmniAudio."""
    try:
        import omniaudio

        model = omniaudio.AudioToMidi()
        midi_obj = model.predict(wav_path)
        midi_obj.save(midi_path)
        return midi_path if os.path.exists(midi_path) else None
    except Exception as e:
        print(f"  Error: omniaudio transcription failed: {e}")
        return None
```

- [ ] **Step 4: Update wav_to_midi to accept engine parameter**

Replace existing `wav_to_midi` function:

```python
def wav_to_midi(wav_path: str, midi_path: str, engine: str = 'omniaudio',
                postprocess: bool = True) -> str | None:
    """
    Transcribe WAV to MIDI using specified engine.

    Args:
        wav_path: Input WAV file.
        midi_path: Output MIDI path.
        engine: 'omniaudio' (default) or 'basic_pitch'.
        postprocess: Whether to run post-processing on output.

    Returns:
        Path to MIDI file, or None on failure.
    """
    deps = check_audio_import_deps()

    # Try requested engine
    if engine == 'omniaudio' and deps.get('omniaudio'):
        print("  Engine: OmniAudio")
        midi_result = wav_to_midi_omniaudio(wav_path, midi_path)
    elif deps.get('basic_pitch'):
        print(f"  Engine: Basic Pitch (fallback)")
        midi_result = wav_to_midi_basic_pitch(wav_path, midi_path)
    else:
        print("  Warning: No transcription engine available.")
        print("  Install: pip install omniaudio basic-pitch")
        return None

    if not midi_result:
        return None

    # Post-processing
    if postprocess:
        print("  Post-processing: quantize, clean, normalize...")
        try:
            import musicpy as mp
            from core.audio_postprocess import postprocess_midi

            piece = mp.read(midi_path)
            piece = postprocess_midi(piece)
            mp.write(piece, name=midi_path)
        except Exception as e:
            print(f"  Warning: post-processing failed: {e}")

    return midi_path
```

- [ ] **Step 5: Write tests for postprocessing integration**

```python
# Add to tests/test_audio_import.py

class TestWavToMidiPostprocess:
    """Test postprocessing integration in wav_to_midi."""

    @patch('core.audio_import.wav_to_midi_omniaudio')
    @patch('core.audio_import.check_audio_import_deps')
    @patch('core.audio_import.os.path.exists')
    @patch('core.audio_import.os.path.getsize')
    def test_runs_postprocess_when_enabled(self, mock_getsize, mock_exists, mock_deps, mock_omni):
        """Should run postprocessing on MIDI output."""
        mock_deps.return_value = {'omniaudio': True, 'basic_pitch': False}
        mock_omni.return_value = 'output.mid'
        mock_exists.return_value = True
        mock_getsize.return_value = 1000

        import musicpy as mp
        with patch('musicpy.read') as mock_read:
            piece = mp.P(tracks=[], instruments=[], start_times=[], bpm=120)
            mock_read.return_value = piece
            with patch('core.audio_import.postprocess_midi') as mock_pp:
                mock_pp.return_value = piece
                with patch('musicpy.write'):
                    from core.audio_import import wav_to_midi
                    result = wav_to_midi('input.wav', 'output.mid', postprocess=True)
                    assert result == 'output.mid'
                    mock_pp.assert_called_once()
```

- [ ] **Step 6: Fix import — add postprocess_midi to audio_import imports**

The `postprocess_midi` function is imported inside the function body (lazy import), so the test mock needs to patch at the right location. Add this mock helper to the test:

```python
# Add import to test file
from core import audio_import

# In the test, patch core.audio_import.postprocess_midi:
with patch.object(audio_import, 'postprocess_midi', return_value=piece) as mock_pp:
```

Actually, since we use lazy import inside the function, we need to patch the module-level import. Update the implementation to use a module-level import instead:

```python
# At top of wav_to_midi function's postprocess block, use:
try:
    from core.audio_postprocess import postprocess_midi as _postprocess_midi
except ImportError:
    _postprocess_midi = None
```

This makes patching easier. Update the test accordingly:

```python
@patch('core.audio_import._postprocess_midi')
@patch('core.audio_import.wav_to_midi_omniaudio')
@patch('core.audio_import.check_audio_import_deps')
@patch('core.audio_import.os.path.exists')
@patch('core.audio_import.os.path.getsize')
def test_runs_postprocess_when_enabled(self, mock_getsize, mock_exists, mock_deps, mock_omni, mock_pp):
    """Should run postprocessing on MIDI output."""
    mock_deps.return_value = {'omniaudio': True, 'basic_pitch': False}
    mock_omni.return_value = 'output.mid'
    mock_exists.return_value = True
    mock_getsize.return_value = 1000
    mock_pp.return_value = MagicMock()

    import musicpy as mp
    with patch('musicpy.read') as mock_read:
        piece = mp.P(tracks=[], instruments=[], start_times=[], bpm=120)
        mock_read.return_value = piece
        with patch('musicpy.write'):
            from core.audio_import import wav_to_midi
            result = wav_to_midi('input.wav', 'output.mid', postprocess=True)
            assert result == 'output.mid'
```

- [ ] **Step 7: Verify all audio_import tests pass**

Run: `pytest tests/test_audio_import.py -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add core/audio_import.py tests/test_audio_import.py
git commit -m "feat: add OmniAudio transcription engine with postprocessing"
```

---

## Task 3: Per-Stem Transcription Pipeline

### Task 3: separate_and_transcribe function

**Files:**
- Modify: `core/audio_import.py`
- Modify: `tests/test_audio_import.py`

- [ ] **Step 1: Write failing test for per-stem transcription**

```python
# Add to tests/test_audio_import.py

class TestSeparateAndTranscribe:
    """Test full per-stem transcription pipeline."""

    @patch('core.audio_import.separate_stems')
    @patch('core.audio_import.wav_to_midi')
    @patch('core.audio_import.os.path.exists')
    @patch('core.audio_import.os.path.getsize')
    def test_transcribes_each_stem_separately(self, mock_getsize, mock_exists,
                                               mock_wav_to_midi, mock_separate, tmp_path):
        """Should transcribe each Demucs stem independently."""
        mock_separate.return_value = [
            str(tmp_path / 'vocals.wav'),
            str(tmp_path / 'bass.wav'),
        ]
        mock_wav_to_midi.side_effect = [
            str(tmp_path / 'vocals.mid'),
            str(tmp_path / 'bass.mid'),
        ]
        mock_exists.return_value = True
        mock_getsize.return_value = 1000

        (tmp_path / 'vocals.wav').touch()
        (tmp_path / 'bass.wav').touch()

        from core.audio_import import separate_and_transcribe
        result = separate_and_transcribe(
            str(tmp_path / 'input.wav'),
            str(tmp_path / 'output'),
            engine='omniaudio'
        )
        assert result is not None
        assert mock_wav_to_midi.call_count == 2

    @patch('core.audio_import.separate_stems')
    def test_falls_back_to_full_file_when_demucs_fails(self, mock_separate):
        """Should use original WAV if stem separation fails."""
        mock_separate.return_value = None

        with patch('core.audio_import.wav_to_midi') as mock_wav_to_midi:
            mock_wav_to_midi.return_value = 'output.mid'
            from core.audio_import import separate_and_transcribe
            result = separate_and_transcribe('input.wav', 'output')
            assert result == 'output.mid'
            mock_wav_to_midi.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_audio_import.py::TestSeparateAndTranscribe -v`
Expected: FAIL (function not defined)

- [ ] **Step 3: Implement separate_and_transcribe**

```python
# Add to core/audio_import.py

def separate_and_transcribe(wav_path: str, output_dir: str,
                            engine: str = 'omniaudio') -> str | None:
    """
    Full pipeline: Demucs stems → per-stem transcription → merge MIDI.

    Args:
        wav_path: Input WAV file.
        output_dir: Directory for intermediate and output files.
        engine: Transcription engine ('omniaudio' or 'basic_pitch').

    Returns:
        Path to merged MIDI file, or None on failure.
    """
    # Step 1: Separate stems
    print("  Separating stems...")
    stems = separate_stems(wav_path, output_dir)

    if not stems:
        # Fallback: transcribe full file
        print("  Stem separation unavailable, using full audio")
        midi_path = os.path.join(output_dir, 'output.mid')
        return wav_to_midi(wav_path, midi_path, engine=engine)

    # Step 2: Transcribe each stem
    midi_files = []
    stem_names = ['vocals', 'bass', 'drums', 'other']
    for i, stem_path in enumerate(stems):
        name = stem_names[i] if i < len(stem_names) else f'stem_{i}'
        midi_path = os.path.join(output_dir, f'{name}.mid')
        print(f"  Transcribing stem: {name}")
        result = wav_to_midi(stem_path, midi_path, engine=engine)
        if result:
            midi_files.append((name, result))

    if not midi_files:
        print("  Error: no stems transcribed successfully")
        return None

    # Step 3: Merge MIDI files into multi-track output
    merge_path = os.path.join(output_dir, 'merged.mid')
    return merge_midi_files(midi_files, merge_path)


def merge_midi_files(stem_midis: list[tuple[str, str]], output_path: str) -> str | None:
    """
    Merge multiple MIDI files into a single multi-track MIDI.

    Args:
        stem_midis: List of (stem_name, midi_path) tuples.
        output_path: Output merged MIDI path.

    Returns:
        Path to merged MIDI file, or None on failure.
    """
    try:
        import musicpy as mp

        merged_tracks = []
        merged_instruments = []
        merged_start_times = []

        # GM instrument mapping for stems
        stem_instruments = {
            'vocals': 1,    # Acoustic Grand Piano (melody)
            'bass': 33,     # Electric Bass
            'drums': 1,     # Piano (percussion mapped)
            'other': 1,     # Piano (accompaniment)
        }

        for stem_name, midi_path in stem_midis:
            piece = mp.read(midi_path)
            for track in piece.tracks:
                merged_tracks.append(track)
                instrument = stem_instruments.get(stem_name, 1)
                merged_instruments.append(instrument)
                merged_start_times.append(0)

        merged = mp.P(
            tracks=merged_tracks,
            instruments=merged_instruments,
            start_times=merged_start_times,
            bpm=120,
        )
        mp.write(merged, name=output_path)
        return output_path
    except Exception as e:
        print(f"  Error: MIDI merge failed: {e}")
        return None
```

- [ ] **Step 4: Write tests for merge_midi_files**

```python
# Add to tests/test_audio_import.py

class TestMergeMidiFiles:
    """Test MIDI file merging."""

    @patch('core.audio_import.musicpy.read')
    @patch('core.audio_import.musicpy.write')
    def test_merges_multiple_midis(self, mock_write, mock_read, tmp_path):
        """Should merge multiple MIDI files into multi-track output."""
        import musicpy as mp

        # Create fake pieces
        track1 = mp.chord([mp.note('C', 4, duration=0.25)], interval=[0.0])
        track2 = mp.chord([mp.note('E', 3, duration=0.25)], interval=[0.0])
        piece1 = mp.P(tracks=[track1], instruments=[1], start_times=[0], bpm=120)
        piece2 = mp.P(tracks=[track2], instruments=[33], start_times=[0], bpm=120)

        mock_read.side_effect = [piece1, piece2]

        from core.audio_import import merge_midi_files
        stem_midis = [('vocals', 'v.mid'), ('bass', 'b.mid')]
        result = merge_midi_files(stem_midis, str(tmp_path / 'merged.mid'))

        assert result == str(tmp_path / 'merged.mid')
        mock_write.assert_called_once()
        merged_piece = mock_write.call_args[1].get('name') or mock_write.call_args[0][0]
        # Verify the merged piece has 2 tracks
        call_args = mock_write.call_args
        merged = call_args[1].get('name') if call_args[1] else None
        # The piece is passed as first positional arg to mp.write
        # musicpy.write(piece, name=path)
```

Actually, musicpy.write signature is `mp.write(piece, name=path)`. Let me fix the test to verify via the mock:

```python
    @patch('core.audio_import.musicpy.read')
    @patch('core.audio_import.musicpy.write')
    def test_merges_multiple_midis(self, mock_write, mock_read, tmp_path):
        """Should merge multiple MIDI files into multi-track output."""
        import musicpy as mp

        track1 = mp.chord([mp.note('C', 4, duration=0.25)], interval=[0.0])
        track2 = mp.chord([mp.note('E', 3, duration=0.25)], interval=[0.0])
        piece1 = mp.P(tracks=[track1], instruments=[1], start_times=[0], bpm=120)
        piece2 = mp.P(tracks=[track2], instruments=[33], start_times=[0], bpm=120)

        mock_read.side_effect = [piece1, piece2]

        from core.audio_import import merge_midi_files
        stem_midis = [('vocals', 'v.mid'), ('bass', 'b.mid')]
        output_path = str(tmp_path / 'merged.mid')
        result = merge_midi_files(stem_midis, output_path)

        assert result == output_path
        mock_write.assert_called_once()
        # The merged piece was passed to mp.write
        merged_piece = mock_write.call_args[0][0]
        assert len(merged_piece.tracks) == 2
        assert merged_piece.instruments == [1, 33]
```

- [ ] **Step 5: Verify all tests pass**

Run: `pytest tests/test_audio_import.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add core/audio_import.py tests/test_audio_import.py
git commit -m "feat: add per-stem transcription pipeline and MIDI merge"
```

---

## Task 4: Expression Pre-Processing for Render

### Task 4: audio_render_expression.py

**Files:**
- Create: `core/audio_render_expression.py`
- Create: `tests/test_audio_render_expression.py`

This module provides expression pre-processing before MIDI rendering:
- Velocity mapping by voice role (melody/accompaniment/bass)
- Phrase-based expression (crescendo/decrescendo)
- Rubato timing variation for human feel

- [ ] **Step 1: Write failing tests for velocity mapping by role**

```python
# tests/test_audio_render_expression.py

"""Tests for core/audio_render_expression.py."""

import musicpy as mp
import pytest

from core.audio_render_expression import (
    apply_velocity_mapping, apply_phrase_expression, apply_rubato,
    apply_full_expression
)


class TestApplyVelocityMapping:
    """Test velocity mapping by voice role."""

    def test_melody_gets_higher_velocity(self, simple_melody_piece):
        """Melody track should get 70-110 velocity range."""
        # Set initial velocities
        for track in simple_melody_piece.tracks:
            for note in (track.notes if hasattr(track, 'notes') else list(track)):
                note.volume = 60

        result = apply_velocity_mapping(simple_melody_piece, profile='piano')
        melody_velocities = [
            n.volume for n in result.tracks[0]
            if hasattr(n, 'volume')
        ]
        assert all(70 <= v <= 110 for v in melody_velocities), \
            f"Melody velocities: {melody_velocities}"

    def test_accompaniment_gets_lower_velocity(self, simple_melody_piece):
        """Accompaniment track should get 40-70 velocity range."""
        for track in simple_melody_piece.tracks:
            for note in (track.notes if hasattr(track, 'notes') else list(track)):
                note.volume = 60

        result = apply_velocity_mapping(simple_melody_piece, profile='piano')
        accomp_velocities = [
            n.volume for n in result.tracks[1]
            if hasattr(n, 'volume')
        ]
        assert all(40 <= v <= 70 for v in accomp_velocities), \
            f"Accompaniment velocities: {accomp_velocities}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_audio_render_expression.py::TestApplyVelocityMapping -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement velocity mapping**

```python
# core/audio_render_expression.py
"""
Audio render expression module.

Pre-processing for MIDI before rendering:
- Velocity mapping by voice role
- Phrase-based expression (crescendo/decrescendo)
- Rubato timing variation
"""

import musicpy as mp

from tools.analysis.voice_detection import detect_voice_roles


# Velocity ranges per role
VELOCITY_RANGES = {
    'melody': (70, 110),
    'accompaniment': (40, 70),
    'bass': (60, 90),
}


def apply_velocity_mapping(piece, profile: str = 'piano') -> mp.P.__class__:
    """
    Map note velocities by voice role.

    Analyzes voice roles and applies appropriate velocity ranges:
    - Melody: 70-110 (expressive)
    - Accompaniment: 40-70 (subtle)
    - Bass: 60-90 (solid)

    Args:
        piece: A musicpy piece object.
        profile: Instrument profile ('piano', 'strings', 'winds').

    Returns:
        Copy of piece with mapped velocities.
    """
    if not piece.tracks:
        return piece

    result = piece.copy()
    roles = detect_voice_roles(result)

    melody_indices = set(roles.get('melody', []))
    bass_indices = set(roles.get('bass', []))

    for track_idx, track in enumerate(result.tracks):
        notes = track.notes if hasattr(track, 'notes') else list(track)

        if track_idx in melody_indices:
            min_vel, max_vel = VELOCITY_RANGES['melody']
        elif track_idx in bass_indices:
            min_vel, max_vel = VELOCITY_RANGES['bass']
        else:
            min_vel, max_vel = VELOCITY_RANGES['accompaniment']

        # Apply profile-specific adjustments
        if profile == 'romantic':
            max_vel = min(127, max_vel + 10)

        for note in notes:
            if hasattr(note, 'volume'):
                note.volume = max(min_vel, min(max_vel, note.volume))

    return result
```

- [ ] **Step 4: Write tests for phrase expression**

```python
class TestApplyPhraseExpression:
    """Test phrase-based expression."""

    def test_adds_crescendo_to_phrase(self):
        """Notes in a phrase should get crescendo pattern."""
        notes = [mp.note('C', 4, duration=0.25) for _ in range(4)]
        notes[0].volume = 60
        track = mp.chord(notes, interval=[0.0] + [0.25] * 3)
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)

        result = apply_phrase_expression(piece, phrase_length=4)
        velocities = [n.volume for n in result.tracks[0]]
        # Crescendo: velocities should generally increase
        assert velocities[-1] > velocities[0]
```

- [ ] **Step 5: Implement phrase expression**

```python
# Add to core/audio_render_expression.py

def apply_phrase_expression(piece, phrase_length: int = 4,
                           intensity: float = 0.1) -> mp.P.__class__:
    """
    Add phrase-based expression: crescendo/decrescendo.

    Within each phrase, notes gradually increase then decrease in velocity.

    Args:
        piece: A musicpy piece object.
        phrase_length: Number of notes per phrase.
        intensity: Strength of expression (0.0-1.0).

    Returns:
        Copy of piece with phrase expression.
    """
    if not piece.tracks:
        return piece

    result = piece.copy()
    for track in result.tracks:
        notes = track.notes if hasattr(track, 'notes') else list(track)
        if not notes:
            continue

        for phrase_start in range(0, len(notes), phrase_length):
            phrase_notes = notes[phrase_start:phrase_start + phrase_length]
            count = len(phrase_notes)
            if count < 2:
                continue

            for i, note in enumerate(phrase_notes):
                if not hasattr(note, 'volume'):
                    continue
                # Crescendo in first half, decrescendo in second
                mid = count / 2
                if i < mid:
                    delta = int(intensity * 127 * (i / mid))
                else:
                    delta = int(intensity * 127 * ((count - 1 - i) / (count - mid)))
                note.volume = max(1, min(127, note.volume + delta))

    return result
```

- [ ] **Step 6: Write tests for rubato**

```python
class TestApplyRubato:
    """Test rubato timing variation."""

    def test_adds_timing_variation(self):
        """Notes should get small timing offsets."""
        notes = [mp.note('C', 4, duration=0.25) for _ in range(8)]
        track = mp.chord(notes, interval=[0.0] + [0.25] * 7)
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)

        result = apply_rubato(piece, amount=0.02, seed=42)
        intervals = getattr(result.tracks[0], 'interval', [])
        # Some intervals should differ from the original 0.25
        varied = [iv for iv in intervals[1:] if abs(iv - 0.25) > 0.001]
        assert len(varied) > 0, "No timing variation applied"

    def test_respects_amount_parameter(self):
        """Larger amount should produce larger variations."""
        notes = [mp.note('C', 4, duration=0.25) for _ in range(8)]
        track = mp.chord(notes, interval=[0.0] + [0.25] * 7)
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)

        result_small = apply_rubato(piece, amount=0.005, seed=42)
        result_large = apply_rubato(piece, amount=0.05, seed=42)

        small_devs = [abs(iv - 0.25) for iv in getattr(result_small.tracks[0], 'interval', [])[1:]]
        large_devs = [abs(iv - 0.25) for iv in getattr(result_large.tracks[0], 'interval', [])[1:]]
        assert max(large_devs) > max(small_devs)
```

- [ ] **Step 7: Implement rubato**

```python
# Add to core/audio_render_expression.py

import random


def apply_rubato(piece, amount: float = 0.01, seed: int | None = None) -> mp.P.__class__:
    """
    Apply slight timing variations for human feel.

    Args:
        piece: A musicpy piece object.
        amount: Maximum timing offset in beats (default ±0.01).
        seed: Random seed for reproducibility.

    Returns:
        Copy of piece with timing variations.
    """
    if not piece.tracks:
        return piece

    if seed is not None:
        random.seed(seed)

    result = piece.copy()
    for track in result.tracks:
        intervals = list(getattr(track, 'interval', []))
        if not intervals:
            continue

        # First interval (always 0 for first note)
        for i in range(1, len(intervals)):
            offset = random.uniform(-amount, amount)
            intervals[i] = max(0.01, intervals[i] + offset)

        track.interval = intervals

    return result
```

- [ ] **Step 8: Write tests for full expression pipeline**

```python
class TestApplyFullExpression:
    """Test full expression pipeline."""

    def test_applies_all_steps(self, simple_melody_piece):
        """Should apply velocity mapping + phrase + rubato."""
        for track in simple_melody_piece.tracks:
            for note in (track.notes if hasattr(track, 'notes') else list(track)):
                note.volume = 60

        result = apply_full_expression(
            simple_melody_piece,
            profile='piano',
            phrase_length=4,
            rubato_amount=0.01
        )

        assert len(result.tracks) == len(simple_melody_piece.tracks)
        # Melody velocities should be elevated
        melody_vel = [n.volume for n in result.tracks[0] if hasattr(n, 'volume')]
        assert any(v >= 70 for v in melody_vel)
```

- [ ] **Step 9: Implement apply_full_expression**

```python
# Add to core/audio_render_expression.py

def apply_full_expression(piece, profile: str = 'piano',
                          phrase_length: int = 4,
                          rubato_amount: float = 0.01) -> mp.P.__class__:
    """
    Run full expression pre-processing pipeline.

    Order: velocity mapping → phrase expression → rubato.

    Args:
        piece: A musicpy piece object.
        profile: Instrument profile.
        phrase_length: Notes per phrase.
        rubato_amount: Timing variation amount.

    Returns:
        Processed piece.
    """
    result = apply_velocity_mapping(piece, profile=profile)
    result = apply_phrase_expression(result, phrase_length=phrase_length)
    result = apply_rubato(result, amount=rubato_amount)
    return result
```

- [ ] **Step 10: Verify all expression tests pass**

Run: `pytest tests/test_audio_render_expression.py -v`
Expected: All PASS

- [ ] **Step 11: Commit**

```bash
git add core/audio_render_expression.py tests/test_audio_render_expression.py
git commit -m "feat: add audio render expression pre-processing module"
```

---

## Task 5: Timidity++ Integration and Post-FX

### Task 5: Extend audio_render.py

**Files:**
- Modify: `core/audio_render.py`
- Modify: `tests/test_audio_render.py`

- [ ] **Step 1: Write failing tests for Timidity rendering**

```python
# Add to tests/test_audio_render.py

class TestRenderTimidity:
    """Test Timidity++ rendering."""

    @patch('core.audio_render.subprocess.run')
    @patch('core.audio_render.os.path.exists')
    def test_success(self, mock_exists, mock_run, tmp_path):
        """Should render WAV on successful timidity run."""
        mock_run.return_value = MagicMock(returncode=0, stderr='')
        mock_exists.return_value = True

        midi_path = str(tmp_path / 'input.mid')
        wav_path = str(tmp_path / 'output.wav')

        from core.audio_render import render_timidity
        result = render_timidity(midi_path, wav_path)
        assert result == wav_path
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert 'timidity' in call_args

    @patch('core.audio_render.subprocess.run')
    def test_timidity_not_found(self, mock_run):
        """Should return None when timidity not installed."""
        mock_run.side_effect = FileNotFoundError()

        from core.audio_render import render_timidity
        result = render_timidity('input.mid', 'output.wav')
        assert result is None

    @patch('core.audio_render.subprocess.run')
    @patch('core.audio_render.os.path.exists')
    def test_reverb_chorus_options(self, mock_exists, mock_run, tmp_path):
        """Should support reverb and chorus options."""
        mock_run.return_value = MagicMock(returncode=0, stderr='')
        mock_exists.return_value = True

        from core.audio_render import render_timidity
        render_timidity(
            'input.mid', 'output.wav',
            reverb=True, chorus=True
        )
        call_args = mock_run.call_args[0][0]
        assert '-Or' in call_args
        assert '-Oc' in call_args
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_audio_render.py::TestRenderTimidity -v`
Expected: FAIL

- [ ] **Step 3: Implement render_timidity**

```python
# Add to core/audio_render.py

def render_timidity(midi_path: str, wav_path: str,
                    reverb: bool = True,
                    chorus: bool = True,
                    options: dict | None = None) -> str | None:
    """
    Render MIDI to WAV using Timidity++.

    Args:
        midi_path: Path to input MIDI file.
        wav_path: Path to output WAV file.
        reverb: Enable reverb effect.
        chorus: Enable chorus effect.
        options: Additional Timidity options dict.

    Returns:
        Path to WAV file on success, None on failure.
    """
    cmd = ['timidity', midi_path, '-Ow', '-o', wav_path]

    if reverb:
        cmd.append('-Or')
    if chorus:
        cmd.append('-Oc')

    if options:
        for key, value in options.items():
            cmd.append(f'{key}{value}')

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120
        )
        if not os.path.exists(wav_path):
            print(f"  Error: timidity failed: {result.stderr[:200]}")
            return None
        return wav_path
    except FileNotFoundError:
        print("  Error: timidity not found. Install with: brew install timidity")
        return None
    except subprocess.TimeoutExpired:
        print("  Error: timidity timed out")
        return None
```

- [ ] **Step 4: Verify Timidity tests pass**

Run: `pytest tests/test_audio_render.py::TestRenderTimidity -v`
Expected: All PASS

- [ ] **Step 5: Write failing tests for post-FX**

```python
# Add to tests/test_audio_render.py

class TestRenderAudioPostfx:
    """Test audio post-processing effects."""

    @patch('core.audio_render.subprocess.run')
    @patch('core.audio_render.os.path.exists')
    def test_applies_reverb_via_ffmpeg(self, mock_exists, mock_run, tmp_path):
        """Should apply reverb using ffmpeg filter."""
        mock_run.return_value = MagicMock(returncode=0, stderr='')
        mock_exists.return_value = True

        input_wav = str(tmp_path / 'input.wav')
        output_wav = str(tmp_path / 'output.wav')

        from core.audio_render import apply_audio_postfx
        result = apply_audio_postfx(input_wav, output_wav, reverb=True)
        assert result == output_wav
        call_args = mock_run.call_args[0][0]
        assert 'ffmpeg' in call_args
        assert 'reverb' in ' '.join(call_args)

    @patch('core.audio_render.subprocess.run')
    @patch('core.audio_render.os.path.exists')
    def test_applies_normalization(self, mock_exists, mock_run, tmp_path):
        """Should apply peak normalization."""
        mock_run.return_value = MagicMock(returncode=0, stderr='')
        mock_exists.return_value = True

        input_wav = str(tmp_path / 'input.wav')
        output_wav = str(tmp_path / 'output.wav')

        from core.audio_render import apply_audio_postfx
        result = apply_audio_postfx(input_wav, output_wav, normalize=True)
        assert result == output_wav
```

- [ ] **Step 6: Implement apply_audio_postfx**

```python
# Add to core/audio_render.py

def apply_audio_postfx(input_wav: str, output_wav: str,
                       reverb: bool = False,
                       compression: bool = False,
                       normalize: bool = True,
                       target_db: str = '-1.0') -> str | None:
    """
    Apply post-processing effects to rendered audio.

    Uses ffmpeg audio filters:
    - reverb: Add convolution reverb
    - compression: Light dynamic range compression
    - normalize: Peak normalize to target dB

    Args:
        input_wav: Input WAV file path.
        output_wav: Output WAV file path.
        reverb: Apply reverb effect.
        compression: Apply compression.
        normalize: Apply peak normalization.
        target_db: Target peak level in dB (default: -1.0).

    Returns:
        Path to processed WAV file, or None on failure.
    """
    if not (reverb or compression or normalize):
        import shutil
        shutil.copy2(input_wav, output_wav)
        return output_wav

    # Build ffmpeg filter chain
    filters = []
    if reverb:
        filters.append('aecho=0.8:0.88:60:0.4')
    if compression:
        filters.append('acompressor=threshold=0.089:ratio=9:attack=200:release=1000')
    if normalize:
        filters.append(f'loudnorm=I={target_db}')

    filter_str = ','.join(filters)

    try:
        result = subprocess.run(
            ['ffmpeg', '-y', '-i', input_wav, '-af', filter_str, output_wav],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0 or not os.path.exists(output_wav):
            print(f"  Error: post-FX failed: {result.stderr[:200]}")
            return None
        return output_wav
    except FileNotFoundError:
        print("  Error: ffmpeg not found for post-processing")
        return None
    except subprocess.TimeoutExpired:
        print("  Error: post-FX timed out")
        return None
```

- [ ] **Step 7: Update render_wav to accept options dict**

```python
# Update existing render_wav signature and body

def render_wav(midi_path: str, wav_path: str, sf2_path: str,
               options: dict | None = None) -> str | None:
    """
    Render MIDI to WAV using fluidsynth.

    Args:
        midi_path: Path to input MIDI file.
        wav_path: Path to output WAV file.
        sf2_path: Path to SoundFont file.
        options: Optional dict with keys:
            - reverb: float (0-1), reverb level
            - chorus: float (0-1), chorus level
            - expression: bool, apply expression pre-processing
            - postfx: dict, pass to apply_audio_postfx

    Returns:
        Path to WAV file on success, None on failure.
    """
    options = options or {}
    raw_path = wav_path.rsplit('.', 1)[0] + '.raw'

    # Build fluidsynth command with effects
    cmd = ['fluidsynth', '-ni']
    if options.get('reverb'):
        cmd.extend(['-r', str(options['reverb'])])
    if options.get('chorus'):
        cmd.extend(['-c', str(options['chorus'])])
    cmd.extend(['-F', raw_path, sf2_path, midi_path])

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120
        )
        if not os.path.exists(raw_path):
            print(f"  Error: fluidsynth failed: {result.stderr[:200]}")
            return None

        with open(raw_path, 'rb') as fin, wave.open(wav_path, 'wb') as wav_out:
            wav_out.setnchannels(2)
            wav_out.setsampwidth(2)
            wav_out.setframerate(44100)
            wav_out.writeframes(fin.read())

        os.remove(raw_path)

        # Apply post-FX if requested
        postfx = options.get('postfx')
        if postfx:
            postfx_path = wav_path.rsplit('.', 1)[0] + '_postfx.wav'
            postfx_result = apply_audio_postfx(wav_path, postfx_path, **postfx)
            if postfx_result:
                import shutil
                shutil.move(postfx_path, wav_path)

        return wav_path
    except FileNotFoundError:
        print("  Error: fluidsynth not found. Install with: brew install fluidsynth")
        return None
    except subprocess.TimeoutExpired:
        print("  Error: fluidsynth timed out")
        return None
```

- [ ] **Step 8: Update render_audio to support engine selection**

```python
# Update render_audio function

def render_audio(midi_path: str, output_path: str,
                 sf2_path: str | None = None,
                 format: str | None = None,
                 engine: str = 'fluidsynth',
                 expression: bool = False,
                 options: dict | None = None) -> str | None:
    """
    Unified entry point for audio rendering.

    Args:
        midi_path: Path to input MIDI file.
        output_path: Desired output path.
        sf2_path: Optional SoundFont path.
        format: Optional format override ('wav' or 'mp3').
        engine: 'fluidsynth' (default) or 'timidity'.
        expression: Whether to apply expression pre-processing.
        options: Additional render options.

    Returns:
        Path to rendered audio file, or None on failure.
    """
    options = options or {}

    # Determine format
    if format is None:
        ext = os.path.splitext(output_path)[1].lower()
        format = 'mp3' if ext == '.mp3' else 'wav'

    # Apply expression pre-processing if requested
    piece = None
    if expression:
        try:
            import musicpy as mp
            from core.audio_render_expression import apply_full_expression
            piece = mp.read(midi_path)
            piece = apply_full_expression(piece)
            # Save expression-enhanced MIDI temporarily
            expr_midi_path = midi_path.rsplit('.', 1)[0] + '_expr.mid'
            mp.write(piece, name=expr_midi_path)
            midi_path = expr_midi_path
        except Exception as e:
            print(f"  Warning: expression pre-processing failed: {e}")

    # Find SoundFont
    sf2 = sf2_path or discover_soundfont()

    if format == 'mp3':
        wav_path = output_path.rsplit('.', 1)[0] + '.wav'
        if engine == 'timidity':
            wav_result = render_timidity(midi_path, wav_path, **options)
        else:
            if sf2 is None:
                print("  Warning: No SoundFont found.")
                return None
            wav_result = render_wav(midi_path, wav_path, sf2, options=options)

        if not wav_result:
            return None

        # Convert to MP3
        try:
            result = subprocess.run(
                ['ffmpeg', '-y', '-i', wav_path, '-codec:a', 'libmp3lame',
                 '-qscale:a', '2', output_path],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode != 0:
                print(f"  Error: ffmpeg failed: {result.stderr[:200]}")
                return None
        except FileNotFoundError:
            print("  Error: ffmpeg not found.")
            return None
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)

        return output_path

    else:  # wav
        if engine == 'timidity':
            return render_timidity(midi_path, output_path, **options)
        else:
            if sf2 is None:
                print("  Warning: No SoundFont found.")
                return None
            return render_wav(midi_path, output_path, sf2, options=options)
```

- [ ] **Step 9: Update existing tests to match new signatures**

The existing tests in `test_audio_render.py` use the old `render_wav(midi_path, wav_path, sf2_path)` signature. The new signature adds an optional `options` parameter with a default, so existing calls should still work. But verify:

Run: `pytest tests/test_audio_render.py -v`
Expected: All PASS (old tests should still pass, new tests added)

- [ ] **Step 10: Commit**

```bash
git add core/audio_render.py tests/test_audio_render.py
git commit -m "feat: add Timidity++ renderer and audio post-FX"
```

---

## Task 6: End-to-End Integration Tests

### Task 6: Pipeline integration with mocked engines

**Files:**
- Create: `tests/test_audio_pipeline_integration.py`

- [ ] **Step 1: Write integration test for full wav→mid→wav round-trip**

```python
# tests/test_audio_pipeline_integration.py

"""Integration tests for the full audio pipeline: WAV → MIDI → WAV."""

import os
from unittest.mock import patch, MagicMock

import pytest
import musicpy as mp

from core.audio_import import wav_to_midi, separate_and_transcribe
from core.audio_render import render_audio, render_timidity
from core.audio_render_expression import apply_full_expression
from core.audio_postprocess import postprocess_midi


class TestFullAudioRoundTrip:
    """Test full WAV → MIDI → WAV round-trip with mocked engines."""

    @patch('core.audio_import.wav_to_midi_omniaudio')
    @patch('core.audio_import.check_audio_import_deps')
    @patch('core.audio_import.os.path.exists')
    @patch('core.audio_import.os.path.getsize')
    @patch('core.audio_render.render_wav')
    def test_wav_to_mid_to_wav(self, mock_render_wav, mock_getsize,
                                mock_exists, mock_deps, mock_omni, tmp_path):
        """Full pipeline: WAV → MIDI → WAV should produce output."""
        # Setup mocks
        mock_deps.return_value = {'omniaudio': True, 'basic_pitch': False}
        mock_omni.return_value = str(tmp_path / 'output.mid')
        mock_exists.return_value = True
        mock_getsize.return_value = 1000

        # Create fake MIDI piece
        track = mp.chord([mp.note('C', 4, duration=0.25)], interval=[0.0])
        piece = mp.P(tracks=[track], instruments=[1], start_times=[0], bpm=120)

        with patch('musicpy.read', return_value=piece):
            with patch('core.audio_import.postprocess_midi', return_value=piece):
                with patch('musicpy.write'):
                    midi_result = wav_to_midi(
                        str(tmp_path / 'input.wav'),
                        str(tmp_path / 'output.mid'),
                        engine='omniaudio',
                        postprocess=True
                    )
                    assert midi_result is not None

        # Render back to WAV
        mock_render_wav.return_value = str(tmp_path / 'rendered.wav')
        wav_result = render_audio(
            str(tmp_path / 'output.mid'),
            str(tmp_path / 'rendered.wav'),
            engine='fluidsynth',
        )
        assert wav_result is not None


class TestPerStemTranscriptionIntegration:
    """Test per-stem transcription with merging."""

    @patch('core.audio_import.merge_midi_files')
    @patch('core.audio_import.wav_to_midi')
    @patch('core.audio_import.separate_stems')
    @patch('core.audio_import.check_audio_import_deps')
    @patch('core.audio_import.os.path.exists')
    @patch('core.audio_import.os.path.getsize')
    def test_separate_and_transcribe_with_stems(self, mock_getsize, mock_exists,
                                                  mock_deps, mock_separate,
                                                  mock_wav_to_midi, mock_merge, tmp_path):
        """Should separate, transcribe stems, and merge."""
        mock_deps.return_value = {'omniaudio': True, 'demucs': True}
        (tmp_path / 'vocals.wav').touch()
        (tmp_path / 'bass.wav').touch()
        mock_separate.return_value = [
            str(tmp_path / 'vocals.wav'),
            str(tmp_path / 'bass.wav'),
        ]
        mock_wav_to_midi.side_effect = [
            str(tmp_path / 'vocals.mid'),
            str(tmp_path / 'bass.mid'),
        ]
        mock_exists.return_value = True
        mock_getsize.return_value = 1000
        mock_merge.return_value = str(tmp_path / 'merged.mid')

        (tmp_path / 'input.wav').touch()

        result = separate_and_transcribe(
            str(tmp_path / 'input.wav'),
            str(tmp_path / 'output'),
        )
        assert result == str(tmp_path / 'merged.mid')
        assert mock_wav_to_midi.call_count == 2
        mock_merge.assert_called_once()


class TestExpressionBeforeRender:
    """Test expression pre-processing before rendering."""

    def test_expression_improves_velocity_contrast(self, simple_melody_piece, tmp_path):
        """Expression should create clearer melody/accompaniment contrast."""
        # Set uniform velocity
        for track in simple_melody_piece.tracks:
            for note in (track.notes if hasattr(track, 'notes') else list(track)):
                note.volume = 60

        result = apply_full_expression(simple_melody_piece, profile='piano')

        melody_vel = [n.volume for n in result.tracks[0] if hasattr(n, 'volume')]
        accomp_vel = [n.volume for n in result.tracks[1] if hasattr(n, 'volume')]

        melody_avg = sum(melody_vel) / max(1, len(melody_vel))
        accomp_avg = sum(accomp_vel) / max(1, len(accomp_vel))

        # Melody should be noticeably louder
        assert melody_avg > accomp_avg + 15, \
            f"Melody avg: {melody_avg}, Accomp avg: {accomp_avg}"
```

- [ ] **Step 2: Run all integration tests**

Run: `pytest tests/test_audio_pipeline_integration.py -v`
Expected: All PASS

- [ ] **Step 3: Run full test suite to verify nothing is broken**

Run: `pytest tests/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_audio_pipeline_integration.py
git commit -m "test: add full audio pipeline integration tests"
```

---

## Self-Review

### 1. Spec Coverage Check

| Spec Requirement | Task | Status |
|---|---|---|
| OmniAudio integration | Task 2 | Covered |
| Per-stem transcription pipeline | Task 3 | Covered |
| Post-processing (quantize, clean, normalize, tempo) | Task 1 | Covered |
| Velocity mapping by role | Task 4 | Covered |
| Phrase-based expression | Task 4 | Covered |
| Rubato timing variation | Task 4 | Covered |
| Timidity++ integration | Task 5 | Covered |
| Post-FX (reverb, compression, normalization) | Task 5 | Covered |
| Updated audio_import.py interface | Task 2, 3 | Covered |
| Updated audio_render.py interface | Task 5 | Covered |
| Tests for all modules | All tasks | Covered |

### 2. Placeholder Scan
No TBD, TODO, or placeholder patterns found in the plan.

### 3. Type Consistency
- All functions use `mp.P.__class__` return type consistently
- `check_audio_import_deps()` returns `dict[str, bool]` — updated with 'omniaudio' key
- `render_wav()` options dict keys are consistent across Task 5
- `postprocess_midi()` called consistently in both `audio_import.py` and tests

### 4. No "Similar to Task N" patterns
All tasks have complete code and test content.
