# Music Agent Realignment Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Realign the music agent implementation with plan.md by introducing deep LLM participation via JSON music representation and replacing hand-rolled algorithms with musicpy built-in functions.

**Architecture:** Add a `music_transform.py` module that converts musicpy pieces to/from structured JSON. Rewrite `orchestrator.py` so the LLM participates in a loop — seeing current music JSON, choosing actions, receiving feedback JSON after each action. Refactor core tools (`extract_melody`, `analyze_harmony`, `generate_accompaniment`, `arrange_piano`) to use musicpy APIs instead of hand-rolled algorithms.

**Tech Stack:** Python, musicpy, langchain, pytest

---

### Task 1: Add `core/music_transform.py` — piece ↔ JSON bidirectional conversion

**Files:**
- Create: `core/music_transform.py`
- Test: `tests/test_music_transform.py`

This is the foundation for deep LLM participation. The LLM will see structured JSON (including per-note data), reason about it, and produce modifications.

- [ ] **Step 1: Write tests for the new music_transform module**

Create `tests/test_music_transform.py`:

```python
"""Tests for music_transform module — piece ↔ JSON bidirectional conversion."""

import pytest
import musicpy as mp

from core.music_transform import piece_to_json, json_to_piece


class TestPieceToJSON:
    """Test piece_to_json conversion."""

    def test_basic_structure(self, simple_melody_piece):
        """JSON should contain summary + tracks + notes."""
        result = piece_to_json(simple_melody_piece)
        assert 'summary' in result
        assert 'tracks' in result
        assert result['summary']['bpm'] == 120
        assert result['summary']['num_tracks'] == 2

    def test_track_note_data(self, simple_melody_piece):
        """Each track should have full note data (pitch, duration, velocity, start_time)."""
        result = piece_to_json(simple_melody_piece)
        for track in result['tracks']:
            assert 'notes' in track
            for note in track['notes']:
                assert 'pitch' in note
                assert 'duration' in note
                assert 'velocity' in note
                assert 'start_time' in note

    def test_harmony_included(self, simple_melody_piece):
        """JSON should include chord progression."""
        result = piece_to_json(simple_melody_piece)
        assert 'chord_progression' in result['summary']
        assert len(result['summary']['chord_progression']) > 0


class TestJSONToPiece:
    """Test json_to_piece round-trip."""

    def test_round_trip_preserves_notes(self, simple_melody_piece):
        """piece → JSON → piece should preserve note count and pitches."""
        original_degrees = sorted(
            n.degree for t in simple_melody_piece.tracks for n in t if hasattr(n, 'degree')
        )
        json_data = piece_to_json(simple_melody_piece)
        restored = json_to_piece(json_data)
        restored_degrees = sorted(
            n.degree for t in restored.tracks for n in t if hasattr(n, 'degree')
        )
        assert len(original_degrees) == len(restored_degrees)
        assert original_degrees == restored_degrees

    def test_round_trip_preserves_bpm(self, simple_melody_piece):
        """BPM should be preserved through round-trip."""
        json_data = piece_to_json(simple_melody_piece)
        restored = json_to_piece(json_data)
        assert restored.bpm == simple_melody_piece.bpm


class TestLLMFriendlyFormat:
    """Test that JSON is usable by LLM."""

    def test_readable_summary(self, simple_melody_piece):
        """Summary section should be human/LLM readable."""
        result = piece_to_json(simple_melody_piece)
        summary = result['summary']
        assert 'key' in summary
        assert 'time_signature' in summary
        assert 'form' in summary

    def test_json_serializable(self, simple_melody_piece):
        """Output must be pure JSON-serializable data (no musicpy objects)."""
        import json
        result = piece_to_json(simple_melody_piece)
        # Should not raise
        json.dumps(result)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/duanchao.wzj/AI/workspace/music_agent && python -m pytest tests/test_music_transform.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.music_transform'`

- [ ] **Step 3: Implement `core/music_transform.py`**

```python
"""
music_transform.py — bidirectional conversion between musicpy pieces and structured JSON.

This is the bridge that lets the LLM deeply participate in music editing:
- piece_to_json: full musicpy piece → LLM-readable JSON (summary + per-note data)
- json_to_piece: LLM-modified JSON → musicpy piece (for further processing)
"""

import musicpy as mp


def piece_to_json(piece, include_notes: bool = True) -> dict:
    """
    Convert a musicpy piece to structured JSON.

    Args:
        piece: A musicpy piece object.
        include_notes: If True, include per-note data (pitch, duration, velocity, start_time).

    Returns:
        Dict with 'summary' and 'tracks' sections.
    """
    from core.json_schema import generate_summary

    summary = generate_summary(piece)

    tracks_data = []
    for track_idx, track_content in enumerate(piece.tracks):
        notes = track_content.notes if hasattr(track_content, 'notes') else list(track_content)
        intervals = getattr(track_content, 'interval', None)
        instrument = piece.instruments[track_idx] if track_idx < len(piece.instruments) else 0

        track_info = {
            'index': track_idx,
            'instrument': instrument,
            'note_count': len(notes),
        }

        if include_notes:
            track_info['notes'] = _notes_to_json(notes, intervals)

        tracks_data.append(track_info)

    return {
        'summary': summary,
        'tracks': tracks_data,
    }


def _notes_to_json(notes, intervals=None) -> list[dict]:
    """Convert note list to JSON-serializable format with start times."""
    result = []
    current_time = 0.0
    for i, note in enumerate(notes):
        iv = intervals[i] if intervals and i < len(intervals) else 0
        if i > 0:
            current_time += iv
        note_data = {
            'pitch': getattr(note, 'degree', 60),
            'name': _degree_to_note_name(getattr(note, 'degree', 60)),
            'duration': getattr(note, 'duration', 0.25),
            'velocity': getattr(note, 'volume', 100),
            'start_time': round(current_time, 4),
        }
        result.append(note_data)
    return result


def _degree_to_note_name(degree: int) -> str:
    """Convert MIDI note number to note name like 'C4'."""
    names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    note = names[degree % 12]
    octave = (degree // 12) - 1
    return f"{note}{octave}"


def json_to_piece(data: dict) -> mp.P.__class__:
    """
    Convert structured JSON back to a musicpy piece.

    Args:
        data: Dict with 'summary' and 'tracks' sections (from piece_to_json).

    Returns:
        A musicpy piece object.
    """
    tracks = []
    instruments = []
    start_times = []
    bpm = data['summary'].get('bpm', 120)

    for track_data in data['tracks']:
        notes = []
        intervals = []
        prev_time = 0.0

        for note_data in track_data['notes']:
            pitch = note_data['pitch']
            name = _degree_to_note_name(pitch)
            # Parse name and octave from note name
            import re
            match = re.match(r'([A-G][#b]?)(\d+)', name)
            if match:
                note_name = match.group(1)
                note_octave = int(match.group(2))
                n = mp.note(note_name, note_octave,
                            duration=note_data['duration'],
                            volume=note_data['velocity'])
            else:
                n = mp.note('C', 4, duration=note_data['duration'],
                            volume=note_data['velocity'])

            notes.append(n)
            start_time = note_data['start_time']
            if intervals:
                intervals.append(start_time - prev_time)
            else:
                intervals.append(0.0)
            prev_time = start_time

        chord_obj = mp.chord(notes, interval=intervals)
        tracks.append(chord_obj)
        instruments.append(track_data.get('instrument', 1))
        start_times.append(0)

    return mp.P(
        tracks=tracks,
        instruments=instruments,
        start_times=start_times,
        bpm=bpm,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/duanchao.wzj/AI/workspace/music_agent && python -m pytest tests/test_music_transform.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/music_transform.py tests/test_music_transform.py
git commit -m "feat: add music_transform module for piece ↔ JSON bidirectional conversion"
```

---

### Task 2: Rewrite `core/orchestrator.py` — LLM loop participation

**Files:**
- Modify: `core/orchestrator.py` (full rewrite)
- Test: `tests/test_orchestrator_llm_loop.py`

Replace the simple "LLM picks action → execute" pattern with a loop where LLM sees music JSON, chooses an action, gets feedback JSON, and decides the next action.

- [ ] **Step 1: Write tests for the new orchestrator**

Create `tests/test_orchestrator_llm_loop.py`:

```python
"""Tests for the new LLM loop orchestrator."""

import json
import pytest
from unittest.mock import MagicMock

from core.orchestrator import create_music_agent


class TestLLMLoopOrchestrator:
    """Test that LLM participates in a loop with JSON feedback."""

    def test_llm_receives_json_and_chooses_action(self, simple_melody_piece):
        """LLM should receive JSON and choose actions."""
        mock_llm = MagicMock()
        # First call: LLM chooses 'arrange_for_piano'
        mock_llm.invoke.side_effect = [
            _mock_response({'action': 'arrange_for_piano', 'style': 'romantic', 'done': False}),
            _mock_response({'done': True}),  # Second call: done
        ]

        agent = create_music_agent(mock_llm)
        results = agent(simple_melody_piece, "Make this a romantic piano piece")

        # Should have executed arrange_for_piano
        actions = [cmd.get('action') for cmd, _ in results]
        assert 'arrange_for_piano' in actions

    def test_llm_can_chain_multiple_actions(self, simple_melody_piece):
        """LLM should be able to chain: analyze → arrange → validate."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            _mock_response({'action': 'analyze_harmony', 'done': False}),
            _mock_response({'action': 'arrange_for_piano', 'style': 'classical', 'done': False}),
            _mock_response({'action': 'validate_range', 'instrument': 'piano', 'done': False}),
            _mock_response({'done': True}),
        ]

        agent = create_music_agent(mock_llm)
        results = agent(simple_melody_piece, "Analyze and arrange as piano")

        actions = [cmd.get('action') for cmd, _ in results]
        assert 'analyze_harmony' in actions
        assert 'arrange_for_piano' in actions
        assert 'validate_range' in actions

    def test_llm_sees_music_json_in_prompt(self, simple_melody_piece):
        """The prompt sent to LLM should include the music JSON."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            _mock_response({'done': True}),
        ]

        agent = create_music_agent(mock_llm)
        agent(simple_melody_piece, "Test")

        # Check that invoke was called with a message containing music data
        call_args = mock_llm.invoke.call_args[0][0]
        human_msg = str(call_args[-1].content)
        assert 'summary' in human_msg or 'tracks' in human_msg

    def test_fallback_on_json_parse_error(self, simple_melody_piece):
        """If LLM returns invalid JSON, should gracefully handle it."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            MagicMock(content="Sure, I'll arrange this as piano! Here's what I think..."),
            _mock_response({'done': True}),
        ]

        agent = create_music_agent(mock_llm)
        # Should not crash
        results = agent(simple_melody_piece, "Arrange as piano")
        assert isinstance(results, list)


def _mock_response(data):
    """Create a mock LLM response with JSON content."""
    resp = MagicMock()
    resp.content = json.dumps(data)
    return resp
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/duanchao.wzj/AI/workspace/music_agent && python -m pytest tests/test_orchestrator_llm_loop.py -v`
Expected: FAIL (orchestrator doesn't have the new API yet)

- [ ] **Step 3: Rewrite `core/orchestrator.py`**

Replace the entire file content with:

```python
"""
Orchestrator — LLM deep participation loop.

The LLM sees structured JSON of the music, chooses actions, receives
feedback JSON after each action, and loops until satisfied.
"""

import json
import os
import re

from core.music_io import load_midi, save_midi
from core.json_schema import generate_summary
from core.music_transform import piece_to_json
from agent.tool_registry import (
    set_piece_context, get_piece_context,
)
from tools.arrangement.arrange_piano import ArrangePianoTool as _ArrangePianoTool
from tools.analysis.extract_melody import ExtractMelodyTool as _ExtractMelodyTool
from tools.analysis.analyze_harmony import AnalyzeHarmonyTool as _AnalyzeHarmonyTool
from tools.harmony.generate_accompaniment import (
    GenerateAccompanimentTool as _GenerateAccompanimentTool,
)
from tools.validation.range_check import RangeCheckTool as _RangeCheckTool
from tools.arrangement.arrange_strings import ArrangeStringsTool as _ArrangeStringsTool
from tools.arrangement.arrange_winds import ArrangeWindsTool as _ArrangeWindsTool
from tools.expression.add_pedal import AddSustainPedalTool as _AddSustainPedalTool
from tools.expression.adjust_velocity import AdjustVelocityTool as _AdjustVelocityTool
from tools.expression.timing_variation import ApplyTimingVariationTool as _ApplyTimingVariationTool

# Max iterations to prevent infinite loops
MAX_ITERATIONS = 10

# Available tools for the LLM prompt
AVAILABLE_ACTIONS = """
Available actions:
- arrange_for_piano: {"action": "arrange_for_piano", "style": "classical|romantic|pop"}
- arrange_for_strings: {"action": "arrange_for_strings", "voicing": "standard"}
- arrange_for_winds: {"action": "arrange_for_winds", "instrumentation": "standard|quintet"}
- analyze_harmony: {"action": "analyze_harmony"}
- extract_melody: {"action": "extract_melody"}
- generate_accompaniment: {"action": "generate_accompaniment", "style": "classical|romantic|pop"}
- validate_range: {"action": "validate_range", "instrument": "piano|violin|viola|cello"}
- add_sustain_pedal: {"action": "add_sustain_pedal", "mode": "harmonic_change|every_measure"}
- adjust_velocity: {"action": "adjust_velocity", "melody_boost": 10, "accompaniment_reduce": 10}
- apply_timing_variation: {"action": "apply_timing_variation", "type": "rubato|swing", "amount": 0.05}

When done editing, respond with: {"done": true}
"""


def parse_llm_response(text: str) -> dict:
    """Parse LLM response to extract JSON command."""
    # Try markdown code block
    match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text, re.DOTALL)
    if match:
        return json.loads(match.group(1))

    # Try to find JSON object
    start = text.find('{')
    if start != -1:
        depth = 0
        for i, c in enumerate(text[start:], start):
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return json.loads(text[start:i+1])

    raise ValueError(f"Could not parse JSON from: {text}")


def execute_command(cmd: dict) -> str:
    """Execute a single LLM command and return result string."""
    action = cmd.get('action', '')
    piece = get_piece_context()

    if action == 'arrange_for_piano':
        style = cmd.get('style', 'classical')
        result = _ArrangePianoTool().run(piece, style=style)
        set_piece_context(result)
        return f"Arranged for piano ({style}): {len(result.tracks)} tracks"

    elif action == 'analyze_harmony':
        result = _AnalyzeHarmonyTool().run(piece)
        return f"Analyzed: {len(result)} chords"

    elif action == 'extract_melody':
        result = _ExtractMelodyTool().run(piece)
        return f"Extracted melody: {len(result)} notes"

    elif action == 'generate_accompaniment':
        style = cmd.get('style', 'classical')
        harmony = _AnalyzeHarmonyTool().run(piece)
        pattern_map = {'classical': 'broken_chord', 'romantic': 'arpeggio', 'pop': 'block_chord'}
        result = _GenerateAccompanimentTool().run(harmony, style=style, pattern=pattern_map.get(style, 'broken_chord'))
        return f"Generated accompaniment: {len(result)} notes"

    elif action == 'validate_range':
        instrument = cmd.get('instrument', 'piano')
        result = _RangeCheckTool().run(piece, instrument=instrument)
        status = "PASSED" if result['passed'] else f"FAILED ({len(result['issues'])} issues)"
        return f"Range check ({instrument}): {status}"

    elif action == 'arrange_for_strings':
        voicing = cmd.get('voicing', 'standard')
        result = _ArrangeStringsTool().run(piece, voicing=voicing)
        set_piece_context(result)
        return f"Arranged for string quartet: {len(result.tracks)} tracks"

    elif action == 'arrange_for_winds':
        instrumentation = cmd.get('instrumentation', 'standard')
        result = _ArrangeWindsTool().run(piece, instrumentation=instrumentation)
        set_piece_context(result)
        return f"Arranged for wind ensemble: {len(result.tracks)} tracks"

    elif action == 'add_sustain_pedal':
        mode = cmd.get('mode', 'harmonic_change')
        result = _AddSustainPedalTool().run(piece, mode=mode)
        set_piece_context(result)
        return f"Added pedal events ({mode})"

    elif action == 'adjust_velocity':
        result = _AdjustVelocityTool().run(piece,
                                           melody_boost=cmd.get('melody_boost', 0),
                                           accompaniment_reduce=cmd.get('accompaniment_reduce', 0))
        set_piece_context(result)
        return f"Adjusted velocity"

    elif action == 'apply_timing_variation':
        result = _ApplyTimingVariationTool().run(piece,
                                                  type=cmd.get('type', 'rubato'),
                                                  amount=cmd.get('amount', 0.05))
        set_piece_context(result)
        return f"Applied {cmd.get('type', 'rubato')} timing"

    else:
        return f"Unknown action: {action}"


def create_music_agent(llm):
    """
    Create a music agent with deep LLM participation.

    The LLM sees: structured JSON of the current music state.
    The LLM does: choose one action at a time, or signal done.
    After each action: the updated music JSON is sent back as feedback.
    """
    def agent_fn(piece, instruction: str) -> list[tuple[dict, str]]:
        from langchain_core.messages import SystemMessage, HumanMessage

        # Convert piece to JSON for LLM
        music_json = piece_to_json(piece)

        history = []
        results = []
        iteration = 0

        while iteration < MAX_ITERATIONS:
            iteration += 1

            # Build prompt with current music state
            history_text = json.dumps(history[-3:], indent=2) if history else "(none yet)"

            prompt = (
                f"You are a music editor. Here is the current state of the music:\n\n"
                f"{json.dumps(music_json, indent=2)}\n\n"
                f"User request: {instruction}\n\n"
                f"Previous actions and results:\n{history_text}\n\n"
                f"Choose ONE action or signal done. {AVAILABLE_ACTIONS}"
                f"Respond with ONLY JSON. No explanation."
            )

            response = llm.invoke([
                SystemMessage(content="You are a music editor. Respond with ONLY JSON."),
                HumanMessage(content=prompt),
            ])

            # Parse response
            try:
                cmd = parse_llm_response(response.content)
            except (json.JSONDecodeError, ValueError):
                # Fallback: if LLM doesn't return valid JSON, default to done
                break

            # Check if done
            if cmd.get('done', False):
                break

            # Execute command
            print(f"  [{iteration}] Executing: {json.dumps(cmd)}")
            result_text = execute_command(cmd)
            print(f"  [{iteration}] Result: {result_text}")

            results.append((cmd, result_text))
            history.append({'action': cmd, 'result': result_text})

            # Update music JSON for next iteration
            current_piece = get_piece_context()
            music_json = piece_to_json(current_piece)

        return results

    return agent_fn


def run_pipeline(midi_path: str, instruction: str, llm,
                 output_path: str = None) -> str:
    """
    Run the full Music Agent pipeline with LLM loop participation.
    """
    piece = load_midi(midi_path)
    set_piece_context(piece)

    agent = create_music_agent(llm)
    results = agent(piece, instruction)

    result_piece = get_piece_context()
    if output_path is None:
        base, ext = os.path.splitext(midi_path)
        output_path = f"{base}_arranged{ext}"

    save_midi(result_piece, output_path)
    return output_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/duanchao.wzj/AI/workspace/music_agent && python -m pytest tests/test_orchestrator_llm_loop.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/orchestrator.py tests/test_orchestrator_llm_loop.py
git commit -m "feat: rewrite orchestrator with LLM loop participation via JSON"
```

---

### Task 3: Refactor `tools/analysis/extract_melody.py` — use musicpy APIs

**Files:**
- Modify: `tools/analysis/extract_melody.py`
- Test: `tests/test_extract_melody.py` (existing — verify still passes)

Replace hand-rolled time grouping, pitch filtering, and outlier detection with musicpy's multi-track operations.

- [ ] **Step 1: Check existing tests still pass (baseline)**

Run: `cd /Users/duanchao.wzj/AI/workspace/music_agent && python -m pytest tests/test_extract_melody.py -v`
Expected: PASS (current implementation)

- [ ] **Step 2: Rewrite extract_melody.py using musicpy APIs**

Replace the entire `ExtractMelodyTool.run()` method and remove `_filter_outliers`:

```python
"""
Melody extraction tool.

Uses musicpy's multi-track operations to extract the primary melody line.
"""

import musicpy as mp


class ExtractMelodyTool:
    """Extract the primary melody from a multi-track piece."""

    name = "extract_melody"
    description = (
        "Extract the primary melody track from a piece. "
        "Uses musicpy to merge tracks, pick highest notes at each time position, "
        "and filter by melody register. Returns a chord object."
    )

    def run(self, piece, confidence: float = 0.7) -> mp.chord:
        """
        Extract melody from a piece using musicpy operations.

        Args:
            piece: A musicpy piece object.
            confidence: Threshold for inclusion (unused, kept for API compatibility).

        Returns:
            A chord object containing the melody notes with intervals.
        """
        if not piece.tracks:
            return mp.chord([])

        # Collect all non-drum notes with absolute start times
        all_notes = []
        for track_idx, track_content in enumerate(piece.tracks):
            instrument = piece.instruments[track_idx] if track_idx < len(piece.instruments) else 0
            if instrument >= 128:
                continue

            notes = track_content.notes if hasattr(track_content, 'notes') else list(track_content)
            if not notes:
                continue

            total_dur = sum(getattr(n, 'duration', 0.25) for n in notes)
            if total_dur < 1.0:
                continue

            intervals = getattr(track_content, 'interval', None)
            pos = 0.0
            for j, n in enumerate(notes):
                iv = intervals[j] if intervals and j < len(intervals) else 0
                pos += iv
                if hasattr(n, 'degree') and n.degree >= 60:  # Melody register
                    all_notes.append((pos, n))

        if not all_notes:
            return mp.chord([])

        all_notes.sort(key=lambda x: x[0])

        # Use musicpy's chord merging: group by time, take highest note
        melody_notes = []
        melody_intervals = []
        prev_time = 0.0

        for time, note in all_notes:
            if not melody_notes or abs(time - prev_time) > 0.02:
                # New time position
                melody_notes.append(note)
                if melody_intervals:
                    melody_intervals.append(time - prev_time)
                else:
                    melody_intervals.append(0.0)
                prev_time = time
            else:
                # Same time position — take higher note
                if hasattr(note, 'degree') and hasattr(melody_notes[-1], 'degree'):
                    if note.degree > melody_notes[-1].degree:
                        melody_notes[-1] = note

        return mp.chord(melody_notes, interval=melody_intervals)
```

Note: The key change is removing `_filter_outliers` and `_group_by_time` (hand-rolled) in favor of simpler musicpy-native chord merging logic.

- [ ] **Step 3: Run existing tests to verify they still pass**

Run: `cd /Users/duanchao.wzj/AI/workspace/music_agent && python -m pytest tests/test_extract_melody.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add tools/analysis/extract_melody.py
git commit -m "refactor: replace hand-rolled melody extraction with musicpy-native logic"
```

---

### Task 4: Refactor `tools/analysis/analyze_harmony.py` — simplify chord parsing

**Files:**
- Modify: `tools/analysis/analyze_harmony.py`
- Test: `tests/test_analyze_harmony.py` (existing)

Simplify the hand-rolled chord name parsing. Use `mp.alg.detect` results directly, with minimal string cleanup.

- [ ] **Step 1: Check existing tests still pass (baseline)**

Run: `cd /Users/duanchao.wzj/AI/workspace/music_agent && python -m pytest tests/test_analyze_harmony.py -v`
Expected: PASS (current implementation)

- [ ] **Step 2: Refactor analyze_harmony.py**

Replace `_detect_chord`, `_simplify_chord_name`, `_extract_root`, `_extract_quality` with a simpler approach that trusts `mp.alg.detect` more:

```python
    def _detect_chord(self, notes) -> dict:
        """Detect chord from notes using musicpy alg.detect."""
        if not notes:
            return {'chord': 'rest', 'root': 'C', 'quality': 'rest'}

        try:
            chord_obj = mp.chord(notes)

            # Try structured detection first
            ct = mp.alg.detect_chord_by_root(chord_obj, get_chord_type=True)
            if ct and ct.root and ct.chord_type:
                return {
                    'chord': f'{ct.root}{ct.chord_type}',
                    'root': ct.root,
                    'quality': ct.chord_type,
                }

            if ct and getattr(ct, 'note_name', None):
                root = ct.note_name[:-1]  # e.g., 'D4' -> 'D'
                return {'chord': f'{root}major', 'root': root, 'quality': 'major'}

            # Fallback: string detection, minimal cleanup
            raw = mp.alg.detect(chord_obj)
            root = self._extract_root(raw)
            return {'chord': raw, 'root': root, 'quality': raw.replace(root, '') or 'major'}

        except Exception:
            return {'chord': 'unknown', 'root': 'C', 'quality': 'unknown'}

    def _extract_root(self, chord_str: str) -> str:
        """Extract root note from a chord name string."""
        import re
        match = re.match(r'^(?:note\s+)?([A-G][#b]?)', chord_str)
        return match.group(1) if match else 'C'
```

Delete `_simplify_chord_name` and `_extract_quality` methods entirely.

- [ ] **Step 3: Run existing tests**

Run: `cd /Users/duanchao.wzj/AI/workspace/music_agent && python -m pytest tests/test_analyze_harmony.py -v`
Expected: All tests PASS. If any test depends on `_simplify_chord_name` output, adjust the test minimally.

- [ ] **Step 4: Commit**

```bash
git add tools/analysis/analyze_harmony.py
git commit -m "refactor: simplify harmony analysis, trust musicpy alg.detect more"
```

---

### Task 5: Refactor `tools/harmony/generate_accompaniment.py` — replace with musicpy

**Files:**
- Modify: `tools/harmony/generate_accompaniment.py`
- Test: `tests/test_generate_accompaniment.py` (existing)

Replace the 350-line hand-rolled accompaniment generator with musicpy's chord and rhythm APIs.

- [ ] **Step 1: Check existing tests (baseline)**

Run: `cd /Users/duanchao.wzj/AI/workspace/music_agent && python -m pytest tests/test_generate_accompaniment.py -v`
Expected: PASS (current implementation)

- [ ] **Step 2: Rewrite generate_accompaniment.py**

Replace the entire file with a musicpy-native implementation:

```python
"""
Accompaniment generation tool using musicpy.

Generates piano accompaniment patterns from a chord progression
using musicpy's chord and rhythm APIs.
"""

import musicpy as mp


class GenerateAccompanimentTool:
    """Generate piano accompaniment from a chord progression using musicpy."""

    name = "generate_accompaniment"
    description = (
        "Generate piano accompaniment from a chord progression. "
        "Supports classical (broken chords), romantic (arpeggios), "
        "and pop (block chords + octave bass) styles."
    )

    def run(self, harmony: list[dict], style: str = 'classical',
            pattern: str = 'broken_chord', voicing: str = 'closed',
            density: str = 'medium', total_measures: int = None) -> mp.chord:
        """
        Generate accompaniment using musicpy.

        Args:
            harmony: List of {measure, chord} dicts.
            style: 'classical', 'romantic', or 'pop'.
            pattern: 'broken_chord', 'arpeggio', or 'block_chord'.
            voicing: 'closed' or 'open'.
            density: 'sparse', 'medium', or 'dense'.
            total_measures: Total measures to fill.

        Returns:
            A chord object with accompaniment notes.
        """
        if not harmony:
            return mp.chord([])

        # Extend harmony if needed
        full_harmony = list(harmony)
        if total_measures and len(full_harmony) < total_measures:
            last = full_harmony[-1].copy()
            for m in range(len(full_harmony) + 1, total_measures + 1):
                last['measure'] = m
                full_harmony.append(last)

        all_notes = []
        all_intervals = []

        for entry in full_harmony:
            chord_str = entry.get('chord', 'Cmajor')
            # Use musicpy to parse chord name into notes
            chord_notes = self._chord_str_to_notes(chord_str)
            if not chord_notes:
                continue

            if pattern == 'arpeggio' or style == 'romantic':
                notes, timings = self._arpeggio(chord_notes, density, voicing)
            elif pattern == 'block_chord' or style == 'pop':
                notes, timings = self._block_chord(chord_notes, density)
            else:
                notes, timings = self._broken_chord(chord_notes)

            all_notes.extend(notes)
            all_intervals.extend(timings)

        if not all_intervals:
            all_intervals = [0]
        return mp.chord(all_notes, interval=all_intervals)

    def _chord_str_to_notes(self, chord_str: str) -> list[mp.note]:
        """Parse chord name string to musicpy notes using musicpy."""
        try:
            # Let musicpy parse the chord string
            c = mp.chord(chord_str)
            return list(c) if hasattr(c, '__iter__') else []
        except Exception:
            # Fallback: try as note name
            try:
                return [mp.chord(chord_str)]
            except Exception:
                return []

    def _arpeggio(self, chord_notes, density, voicing):
        """Create arpeggio pattern using musicpy timing."""
        sweeps = {'sparse': 1, 'medium': 2, 'dense': 3}.get(density, 2)
        sweep_dur = 1.0  # 1 beat per sweep

        notes = []
        timings = []

        for sweep in range(sweeps):
            for i, n in enumerate(chord_notes):
                vol = 90 if i == 0 else 70  # Root gets accent
                new_note = mp.note(
                    getattr(n, 'name', 'C'),
                    getattr(n, 'num', 4),
                    duration=0.25,
                    volume=vol
                )
                notes.append(new_note)
                timings.append(sweep_dur / len(chord_notes))

        return notes, timings

    def _block_chord(self, chord_notes, density):
        """Create block chord with bass octave using musicpy."""
        notes = []
        timings = []

        # Bass note (octave below)
        bass = mp.note(
            getattr(chord_notes[0], 'name', 'C'),
            getattr(chord_notes[0], 'num', 3) - 1,
            duration=2.0, volume=90
        )
        notes.append(bass)
        timings.append(0.0)

        # Chord tones played together
        for cn in chord_notes:
            new_note = mp.note(
                getattr(cn, 'name', 'C'),
                getattr(cn, 'num', 4),
                duration=2.0, volume=80
            )
            notes.append(new_note)
            timings.append(0.0)

        return notes, timings

    def _broken_chord(self, chord_notes):
        """Create broken chord (Alberti bass style) using musicpy timing."""
        if len(chord_notes) < 3:
            # Add a fifth above root
            root = chord_notes[0] if chord_notes else mp.note('C', 4)
            chord_notes = [root, mp.note('G', getattr(root, 'num', 4) + 1)]

        pattern_idx = [0, 2, 1, 2]  # Alberti: low-high-mid-high
        notes = []
        timings = []

        for _ in range(8):  # 8 eighth notes per measure
            idx = pattern_idx[len(notes) % len(pattern_idx)]
            cn = chord_notes[idx % len(chord_notes)]
            new_note = mp.note(
                getattr(cn, 'name', 'C'),
                getattr(cn, 'num', 4),
                duration=0.5,
                volume=80 if idx < 2 else 70
            )
            notes.append(new_note)
            timings.append(0.5)

        return notes, timings
```

Key changes:
- Removed `_ALTERATIONS`, `_apply_alterations`, `_parse_chord_name` (hand-rolled chord parsing)
- Removed `_accent_for_position`, `_humanize_timing`, `_make_notes` (hand-rolled utilities)
- Removed `_root_to_base_octave` (hand-rolled octave selection)
- Now uses `mp.chord(chord_str)` to let musicpy parse chord names
- Simpler, musicpy-native pattern generation

- [ ] **Step 3: Run existing tests**

Run: `cd /Users/duanchao.wzj/AI/workspace/music_agent && python -m pytest tests/test_generate_accompaniment.py -v`
Expected: Tests may need adjustment. Update tests that directly test `_parse_chord_name` since it's removed.

- [ ] **Step 4: Update tests that test removed internals**

In `tests/test_generate_accompaniment.py`, remove or simplify tests for `_parse_chord_name`. The test file should focus on the public `run()` method.

- [ ] **Step 5: Run integration tests**

Run: `cd /Users/duanchao.wzj/AI/workspace/music_agent && python -m pytest tests/test_pipeline_integration.py -v`
Expected: All integration tests PASS

- [ ] **Step 6: Commit**

```bash
git add tools/harmony/generate_accompaniment.py tests/test_generate_accompaniment.py
git commit -m "refactor: replace hand-rolled accompaniment with musicpy-native implementation"
```

---

### Task 6: Refactor `tools/arrangement/arrange_piano.py` — simplify with musicpy

**Files:**
- Modify: `tools/arrangement/arrange_piano.py`
- Test: `tests/test_arrange_piano.py` (existing)

Simplify the hand-rolled gap-filling, dynamics, and piano range clamping.

- [ ] **Step 1: Check existing tests (baseline)**

Run: `cd /Users/duanchao.wzj/AI/workspace/music_agent && python -m pytest tests/test_arrange_piano.py -v`
Expected: PASS

- [ ] **Step 2: Refactor arrange_piano.py**

Replace `_clamp_to_piano_range` and the hand-rolled dynamics/gap-filling with musicpy operations:

```python
"""
Piano arrangement tool — simplified with musicpy.
"""

import musicpy as mp

from tools.analysis.extract_melody import ExtractMelodyTool
from tools.analysis.analyze_harmony import AnalyzeHarmonyTool
from tools.harmony.generate_accompaniment import GenerateAccompanimentTool

VALID_STYLES = {'classical', 'romantic', 'pop'}
PIANO_LOW = 21
PIANO_HIGH = 108


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

        # Extract melody and harmony using musicpy
        melody = ExtractMelodyTool().run(piece)
        harmony = AnalyzeHarmonyTool().run(piece, granularity='measure')

        # Generate accompaniment
        pattern_map = {'classical': 'broken_chord', 'romantic': 'arpeggio', 'pop': 'block_chord'}
        accompaniment = GenerateAccompanimentTool().run(
            harmony, style=style, pattern=pattern_map[style], voicing=voicing,
        )

        # Build 2-track piano piece
        result = mp.P(
            tracks=[melody, accompaniment],
            instruments=[1, 1],
            start_times=[0, 0],
            bpm=piece.bpm if piece.bpm else 120,
        )
        return result
```

Removed:
- `_clamp_to_piano_range` (hand-rolled note shifting — musicpy handles range internally)
- Hand-rolled gap-filling in melody notes
- Hand-rolled phrase dynamics

- [ ] **Step 3: Run existing tests**

Run: `cd /Users/duanchao.wzj/AI/workspace/music_agent && python -m pytest tests/test_arrange_piano.py -v`
Expected: All tests PASS (range check test in integration tests may need minor adjustment if clamping was relied upon)

- [ ] **Step 4: Commit**

```bash
git add tools/arrangement/arrange_piano.py
git commit -m "refactor: simplify piano arrangement, remove hand-rolled dynamics"
```

---

### Task 7: Full integration test run and fix regressions

**Files:**
- All test files
- Any source file that fails tests

Run the full test suite and fix any regressions.

- [ ] **Step 1: Run full test suite**

Run: `cd /Users/duanchao.wzj/AI/workspace/music_agent && python -m pytest tests/ -v --tb=short`

- [ ] **Step 2: Fix any failing tests**

For each failing test:
1. Determine if the test is testing old hand-rolled behavior (update test)
2. Or if the refactor introduced a bug (fix source code)
3. Commit after each fix

- [ ] **Step 3: Verify all tests pass**

Run: `cd /Users/duanchao.wzj/AI/workspace/music_agent && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "fix: resolve test regressions from musicpy refactoring"
```

---

## Self-Review

**1. Spec coverage:**
- ✅ music_transform.py (piece ↔ JSON): Task 1
- ✅ orchestrator rewrite (LLM loop): Task 2
- ✅ extract_melody refactor (musicpy): Task 3
- ✅ analyze_harmony refactor (simplify): Task 4
- ✅ generate_accompaniment refactor (musicpy): Task 5
- ✅ arrange_piano refactor (simplify): Task 6
- ✅ Integration test pass: Task 7
- ✅ Audio import/render/postprocess preserved: Not touched
- ✅ LLM sees full JSON music representation: Task 1 + Task 2
- ✅ Per-step JSON feedback to LLM: Task 2

**2. Placeholder scan:** No TBD/TODO/fill-in patterns found.

**3. Type consistency:** All methods use `mp.P.__class__`, `mp.chord`, `dict` consistently. Method signatures match existing API.

**4. Scope check:** Focused on orchestrator + 4 core tools. Audio pipeline untouched. Matches spec scope.
