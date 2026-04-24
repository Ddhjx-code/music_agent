# Multi-Role Music Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-LLM flat action loop with a 6-role collaboration pipeline (Planner, Analyst, Arranger, Harmonist, Expression, Critic) where each role has its own LLM call, prompt template, and tool subset.

**Architecture:** Each role is a standalone module in `core/roles/` with a `run(piece, context)` method. The `RoleOrchestrator` manages phase transitions and Critic bounce-back. Tools are decoupled so Arranger no longer internally calls Analysis tools.

**Tech Stack:** Python, musicpy, langchain-core, existing tool infrastructure, prompt templates from `prompts/`

---

### Task 1: Create Role base class and context structure

**Files:**
- Create: `core/roles/__init__.py` (Task 5 — not Task 1, imports depend on roles existing)
- Create: `core/roles/base.py`
- Create: `core/roles/utils.py` (shared JSON extraction utility)

- [ ] **Step 1: Write `core/roles/base.py` with Role abstract class and context helper**

```python
"""
Base class for music agent roles.

Each role has a name, prompt template, tool list, max iterations,
and a run(piece, context) -> dict method.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import musicpy as mp


class RoleContext:
    """Structured context passed between roles."""

    def __init__(self, instruction: str):
        self.instruction = instruction
        self.plan: dict | None = None
        self.analyst_report: dict | None = None
        self.arrangement_report: dict | None = None
        self.harmony_report: dict | None = None
        self.expression_report: dict | None = None
        self.critic_issues: list[dict] | None = None

    def to_prompt_context(self) -> dict:
        """Convert to dict for prompt templating."""
        return {
            "instruction": self.instruction,
            "plan": self.plan,
            "analyst_report": self.analyst_report,
            "arrangement_report": self.arrangement_report,
            "harmony_report": self.harmony_report,
            "expression_report": self.expression_report,
            "critic_issues": self.critic_issues,
        }


class Role(ABC):
    name: str
    max_iterations: int = 1

    @abstractmethod
    def run(self, piece: mp.P, context: RoleContext, llm) -> tuple[mp.P, dict]:
        """Execute role task. Returns (updated_piece, structured_report)."""
        ...
```

- [ ] **Step 2: Write `core/roles/__init__.py`** (moved to Task 5 Step 7, after all roles exist)

Skip this step for now — see Task 5 Step 7.
```

- [ ] **Step 2: Write `core/roles/utils.py` with shared JSON extraction helper**

```python
"""Shared utilities for roles."""

import json
import re


def extract_json(text: str, fallback: dict | None = None) -> dict:
    """Extract JSON from LLM response text.

    Tries markdown code block first, then raw JSON object.
    Returns fallback dict if no JSON found.
    """
    if fallback is None:
        fallback = {}
    match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    start = text.find('{')
    if start != -1:
        depth = 0
        for i, c in enumerate(text[start:], start):
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i+1])
                    except json.JSONDecodeError:
                        pass
    return fallback
```

- [ ] **Step 3: Commit**

```bash
git add core/roles/base.py core/roles/utils.py
git commit -m "feat: add Role base class, RoleContext, and shared JSON extraction utility"
```

---

### Task 2: Create 6 prompt templates

**Files:**
- Create: `prompts/planner.md`
- Create: `prompts/analyst.md`
- Create: `prompts/arranger.md`
- Create: `prompts/harmonist.md`
- Create: `prompts/expression.md`
- Create: `prompts/critic.md`

- [ ] **Step 1: Write `prompts/planner.md`**

```markdown
# Planner — Route Controller

Parse the user request and produce an execution plan.

## Input
- User instruction: {instruction}
- Analysis report: {analyst_report}

## Available phases
- analysis: Extract melody, harmony, voice roles, range check
- arrangement: Arrange for piano/strings/winds
- harmonist: Generate accompaniment from chord progression (optional, needs arrangement first)
- expression: Adjust velocity, timing, add pedal

## Output Format (JSON only)
{{
  "phases": ["analysis", "arrangement", "expression"],
  "params": {{
    "arrangement": {{"instrument": "piano", "style": "classical"}},
    "harmonist": {{"style": "classical", "pattern": "broken_chord"}},
    "expression": {{"melody_boost": 10, "accompaniment_reduce": 10, "timing": "rubato"}}
  }}
}}

Rules:
- "analysis" is always first
- "expression" is always last (if any arrangement was done)
- "harmonist" is optional — only include if the arrangement needs accompaniment
- Match the instrument/style to the user's request
- If user says "arrange for piano", use arrangement.instrument = "piano"
- If user says "classical", use style = "classical"
- If user says "romantic", use style = "romantic"
- If user says "pop", use style = "pop"
```

- [ ] **Step 2: Write `prompts/analyst.md`**

```markdown
# Analyst — Music Analyst

Analyze the piece and produce a structured diagnostic report.

## Input
- Music state: {music_json}
- ABC notation (K:C): {abc_notation}

## Output Format (JSON only)
{{
  "melody": {{"notes_count": N, "range": "C4-G5", "track_indices": [0]}},
  "harmony": [{{"measure": 1, "chord": "Cmaj7"}}, ...],
  "voice_roles": {{"melody": [0], "harmony": [1], "bass": [2]}},
  "range_issues": [],
  "summary": "brief description of the piece"
}}

Rules:
- melody: identify the highest-pitch melodic line
- harmony: list the chord progression per measure
- voice_roles: classify tracks by pitch position
- range_issues: flag notes outside typical instrument ranges
- This is a read-only analysis — do not modify the piece
```

- [ ] **Step 3: Write `prompts/arranger.md`**

```markdown
# Arranger — Instrumental Arranger

Arrange the piece based on the execution plan and analysis report.

## Input
- Music state: {music_json}
- Analysis report: {analyst_report}
- Plan: {plan}
- Previous attempt issues: {critic_issues}

## Available actions
- arrange_for_piano: {{"action": "arrange_for_piano", "style": "classical|romantic|pop"}}
- arrange_for_strings: {{"action": "arrange_for_strings", "voicing": "standard"}}
- arrange_for_winds: {{"action": "arrange_for_winds", "instrumentation": "standard|quintet"}}

## Output Format
Choose ONE action from the available actions based on the plan params.
Respond with JSON: {{"action": "...", "params": {{...}}}}
Or signal done: {{"done": true}}

Do NOT repeat the same action.
```

- [ ] **Step 4: Write `prompts/harmonist.md`**

```markdown
# Harmonist — Accompaniment Generator

Generate accompaniment from the chord progression.

## Input
- Music state: {music_json}
- Analysis report: {analyst_report}
- Plan params: {plan}
- Previous attempt issues: {critic_issues}

## Available actions
- generate_accompaniment: {{"action": "generate_accompaniment", "style": "classical|romantic|pop", "pattern": "broken_chord|arpeggio|block_chord"}}

## Output Format
Choose ONE action. Respond with JSON.
Or signal done: {{"done": true}}
```

- [ ] **Step 5: Write `prompts/expression.md`**

```markdown
# Expression — Dynamic Expression Engineer

Add musical expression: velocity, timing, pedal.

## Input
- Music state: {music_json}
- Previous reports: {arrangement_report}, {harmony_report}
- Previous attempt issues: {critic_issues}

## Available actions
- adjust_velocity: {{"action": "adjust_velocity", "melody_boost": 10, "accompaniment_reduce": 10}}
- apply_timing_variation: {{"action": "apply_timing_variation", "type": "rubato|swing", "amount": 0.05}}
- add_sustain_pedal: {{"action": "add_sustain_pedal", "mode": "harmonic_change|every_measure"}}

## Output Format
Choose ONE action. Respond with JSON.
Or signal done: {{"done": true}}

Do NOT repeat the same action.
```

- [ ] **Step 6: Write `prompts/critic.md`**

```markdown
# Critic — Quality Reviewer

Review the final piece and all role reports for quality issues.

## Input
- Music state: {music_json}
- All reports: {analyst_report}, {arrangement_report}, {harmony_report}, {expression_report}

## Review Criteria
1. **Range check**: All notes within instrument range
2. **Harmony consistency**: Chord progression is musically coherent
3. **Dynamic balance**: Melody is louder than accompaniment
4. **Structural integrity**: No orphan notes, reasonable note density

## Output Format (JSON only)
{{
  "passed": true/false,
  "issues": [
    {{
      "role": "arranger|harmonist|expression",
      "severity": "high|medium|low",
      "description": "what is wrong",
      "fix_instruction": "what to do to fix it"
    }}
  ]
}}

Rules:
- If passed is true, issues should be empty
- high severity = must fix before output
- medium severity = should fix, but can proceed if time-limited
- low severity = cosmetic, note for future improvement
```

- [ ] **Step 7: Delete `prompts/orchestrator.md`** (replaced by role-specific prompts)

- [ ] **Step 8: Commit**

```bash
git add prompts/planner.md prompts/analyst.md prompts/arranger.md prompts/harmonist.md prompts/expression.md prompts/critic.md
git rm prompts/orchestrator.md
git commit -m "feat: add 6 role prompt templates, remove orchestrator.md"
```

---

### Task 3: Decouple ArrangePianoTool from internal Analysis calls

**Files:**
- Modify: `tools/arrangement/arrange_piano.py`

**Goal:** Remove internal `ExtractMelodyTool` and `AnalyzeHarmonyTool` calls. Instead, accept pre-extracted melody and harmony as parameters.

- [ ] **Step 1: Rewrite `tools/arrangement/arrange_piano.py`**

```python
"""
Piano arrangement tool — decoupled version.

Accepts pre-extracted melody and harmony data from Analyst.
No longer calls ExtractMelodyTool or AnalyzeHarmonyTool internally.
"""

import musicpy as mp

from tools.harmony.generate_accompaniment import GenerateAccompanimentTool

VALID_STYLES = {'classical', 'romantic', 'pop'}


class ArrangePianoTool:
    """Arrange any piece for piano solo."""

    name = "arrange_for_piano"
    description = (
        "Arrange a piece for piano solo using pre-extracted melody (RH) "
        "and harmony data to generate accompaniment (LH). "
        "Styles: classical, romantic, pop."
    )

    def run(self, piece, melody: mp.chord, harmony: list[dict],
            style: str = 'classical',
            voicing: str = 'closed') -> mp.P:
        """Arrange for piano using pre-extracted melody and harmony."""
        if style not in VALID_STYLES:
            raise ValueError(
                f"Invalid style '{style}'. Must be: {', '.join(sorted(VALID_STYLES))}"
            )

        pattern_map = {
            'classical': 'broken_chord',
            'romantic': 'arpeggio',
            'pop': 'block_chord',
        }
        accompaniment = GenerateAccompanimentTool().run(
            harmony,
            style=style,
            pattern=pattern_map[style],
            voicing=voicing,
        )

        result = mp.P(
            tracks=[melody, accompaniment],
            instruments=[1, 1],
            start_times=[0, 0],
            bpm=piece.bpm if piece.bpm else 120,
        )
        return result
```

- [ ] **Step 2: Commit**

```bash
git add tools/arrangement/arrange_piano.py
git commit -m "refactor: decouple ArrangePianoTool from internal Analysis calls"
```

---

### Task 4: Decouple GenerateAccompanimentTool and AdjustVelocityTool

**Files:**
- Modify: `tools/harmony/generate_accompaniment.py` — no changes needed, already accepts harmony data directly. The coupling was in orchestrator.py `execute_command`. We document this is already decoupled.
- Modify: `tools/expression/adjust_velocity.py` — accept `voice_roles` parameter

- [ ] **Step 1: Rewrite `tools/expression/adjust_velocity.py` to accept voice_roles**

```python
"""
Velocity adjustment tool.

Adjusts note velocities (volumes) to create dynamic contrast:
- Boost melody track velocity
- Reduce accompaniment track velocity
This creates clearer melody/accompaniment separation in the mix.
"""

import musicpy as mp


class AdjustVelocityTool:
    """Adjust note velocities for dynamic balance."""

    name = "adjust_velocity"
    description = (
        "Adjust note velocities to create dynamic contrast between "
        "melody and accompaniment. "
        "Args: voice_roles (dict) - from Analyst {melody: [idxs], ...}, "
        "melody_boost (int) - velocity increase for melody track (default 10), "
        "accompaniment_reduce (int) - velocity decrease for accompaniment tracks (default 10). "
        "Returns the piece with adjusted velocities."
    )

    def run(self, piece, voice_roles: dict | None = None,
            melody_boost: int = 10,
            accompaniment_reduce: int = 10) -> mp.P:
        """
        Adjust note velocities.

        Args:
            piece: A musicpy piece object.
            voice_roles: Dict from Analyst {melody: [idxs], harmony: [idxs], ...}.
                        If None, auto-detect via detect_voice_roles.
            melody_boost: Amount to add to melody track velocity.
            accompaniment_reduce: Amount to subtract from accompaniment tracks.

        Returns:
            The piece with adjusted velocities.
        """
        if not piece.tracks or (melody_boost == 0 and accompaniment_reduce == 0):
            return piece

        result = piece.copy()

        if voice_roles:
            melody_indices = set(voice_roles.get('melody', []))
        else:
            from tools.analysis.voice_detection import detect_voice_roles
            roles = detect_voice_roles(piece)
            melody_indices = set(roles.get('melody', []))

        for track_idx, track in enumerate(result.tracks):
            notes = track.notes if hasattr(track, 'notes') else list(track)
            if track_idx in melody_indices:
                adjustment = melody_boost
            else:
                adjustment = -accompaniment_reduce

            for note in notes:
                if hasattr(note, 'volume'):
                    new_vel = note.volume + adjustment
                    note.volume = max(1, min(127, new_vel))

        return result
```

- [ ] **Step 2: Commit**

```bash
git add tools/expression/adjust_velocity.py
git commit -m "refactor: AdjustVelocityTool accepts voice_roles from Analyst"
```

---

### Task 5: Implement the 6 Role modules

**Files:**
- Create: `core/roles/planner_role.py`
- Create: `core/roles/analyst_role.py`
- Create: `core/roles/arranger_role.py`
- Create: `core/roles/harmonist_role.py`
- Create: `core/roles/expression_role.py`
- Create: `core/roles/critic_role.py`
- Modify: `core/roles/__init__.py`

- [ ] **Step 1: Write `core/roles/planner_role.py`**

```python
"""Planner role — parse user instruction into execution plan."""

from __future__ import annotations

import json

import musicpy as mp

from core.roles.base import Role, RoleContext


class PlannerRole(Role):
    name = "planner"
    max_iterations = 1

    def run(self, piece: mp.P, context: RoleContext, llm) -> tuple[mp.P, dict]:
        """Parse instruction + analyst report into a plan. Does not modify piece."""
        from core.prompt_loader import load_prompt
        from core.roles.utils import extract_json
        from langchain_core.messages import SystemMessage, HumanMessage

        template = load_prompt("planner")
        prompt = template.format(
            instruction=context.instruction,
            analyst_report=json.dumps(context.analyst_report, indent=2, ensure_ascii=False)
            if context.analyst_report else "(no analysis yet)",
        )

        response = llm.invoke([
            SystemMessage(content="You are a music production planner. Output ONLY JSON."),
            HumanMessage(content=prompt),
        ])

        raw = getattr(response, 'content', '')
        plan = extract_json(raw, {"phases": ["analysis", "arrangement", "expression"], "params": {}})
        context.plan = plan

        print(f"\n[Planner] Plan: {json.dumps(plan, indent=2)}")
        return piece, plan
```

- [ ] **Step 2: Write `core/roles/analyst_role.py`**

```python
"""Analyst role — extract melody, harmony, voice roles, range check."""

from __future__ import annotations

import json

import musicpy as mp

from core.roles.base import Role, RoleContext


class AnalystRole(Role):
    name = "analyst"
    max_iterations = 1

    def run(self, piece: mp.P, context: RoleContext, llm) -> tuple[mp.P, dict]:
        """Analyze piece and produce structured report. Does not modify piece."""
        from tools.analysis.extract_melody import ExtractMelodyTool
        from tools.analysis.analyze_harmony import AnalyzeHarmonyTool
        from tools.validation.range_check import RangeCheckTool
        from tools.analysis.voice_detection import detect_voice_roles
        from core.prompt_loader import load_prompt
        from core.roles.utils import extract_json
        from langchain_core.messages import SystemMessage, HumanMessage

        # Run analysis tools directly (no LLM needed for raw analysis)
        melody = ExtractMelodyTool().run(piece)
        harmony = AnalyzeHarmonyTool().run(piece, granularity='measure')
        voice_roles = detect_voice_roles(piece)
        range_result = RangeCheckTool().run(piece, instrument='piano')

        # Build tool analysis report
        tool_report = {
            "melody": {
                "notes_count": len(melody) if hasattr(melody, '__len__') else 0,
                "track_indices": [],
            },
            "harmony": harmony,
            "voice_roles": voice_roles,
            "range_issues": range_result.get('issues', []),
            "range_passed": range_result.get('passed', True),
        }

        context.analyst_report = tool_report
        print(f"\n[Analyst] Report: {json.dumps(tool_report, indent=2, ensure_ascii=False)[:500]}...")
        return piece, tool_report

    def run_tools_only(self, piece: mp.P, context: RoleContext) -> tuple[mp.P, dict]:
        """Run analysis tools without LLM (for pre-analysis before Planner)."""
        return self.run(piece, context, llm=None)
```

- [ ] **Step 3: Write `core/roles/arranger_role.py`**

```python
"""Arranger role — arrange piece for target instrumentation."""

from __future__ import annotations

import json

import musicpy as mp

from core.roles.base import Role, RoleContext


class ArrangerRole(Role):
    name = "arranger"
    max_iterations = 2

    def run(self, piece: mp.P, context: RoleContext, llm) -> tuple[mp.P, dict]:
        """Arrange piece according to plan. Max 2 iterations."""
        from core.prompt_loader import load_prompt
        from core.roles.utils import extract_json
        from langchain_core.messages import SystemMessage, HumanMessage
        from core.music_transform import piece_to_json
        from agent.tool_registry import set_piece_context

        template = load_prompt("arranger")
        set_piece_context(piece)
        iteration = 0
        used_actions = set()
        report = {"actions": [], "tracks_before": len(piece.tracks)}

        while iteration < self.max_iterations:
            iteration += 1
            music_json = piece_to_json(piece)
            critic_issues = json.dumps(context.critic_issues, indent=2) if context.critic_issues else "(none)"

            prompt = template.format(
                music_json=json.dumps(music_json, indent=2, ensure_ascii=False),
                analyst_report=json.dumps(context.analyst_report, indent=2, ensure_ascii=False),
                plan=json.dumps(context.plan, indent=2, ensure_ascii=False),
                critic_issues=critic_issues,
            )

            response = llm.invoke([
                SystemMessage(content="You are a music arranger. Output ONLY JSON."),
                HumanMessage(content=prompt),
            ])

            cmd = extract_json(getattr(response, 'content', ''))
            if not cmd or cmd.get('done', False):
                break

            action_key = cmd.get('action', '')
            if action_key in used_actions:
                break
            used_actions.add(action_key)

            print(f"  [Arranger iter {iteration}] Executing: {json.dumps(cmd)}")
            piece = _execute_arrange(piece, cmd, context)
            set_piece_context(piece)
            report["actions"].append(cmd)

        report["tracks_after"] = len(piece.tracks)
        context.arrangement_report = report
        print(f"\n[Arranger] Done: {report}")
        return piece, report


def _execute_arrange(piece: mp.P, cmd: dict, context: RoleContext) -> mp.P:
    """Execute an arrangement action."""
    action = cmd.get('action', '')

    if action == 'arrange_for_piano':
        from tools.arrangement.arrange_piano import ArrangePianoTool
        from tools.analysis.extract_melody import ExtractMelodyTool
        from tools.analysis.analyze_harmony import AnalyzeHarmonyTool

        melody = ExtractMelodyTool().run(piece)
        harmony = AnalyzeHarmonyTool().run(piece, granularity='measure')
        style = cmd.get('style', 'classical')
        return ArrangePianoTool().run(piece, melody=melody, harmony=harmony, style=style)

    elif action == 'arrange_for_strings':
        from tools.arrangement.arrange_strings import ArrangeStringsTool
        voicing = cmd.get('voicing', 'standard')
        return ArrangeStringsTool().run(piece, voicing=voicing)

    elif action == 'arrange_for_winds':
        from tools.arrangement.arrange_winds import ArrangeWindsTool
        instrumentation = cmd.get('instrumentation', 'standard')
        return ArrangeWindsTool().run(piece, instrumentation=instrumentation)

    return piece
```

- [ ] **Step 4: Write `core/roles/harmonist_role.py`**

```python
"""Harmonist role — generate accompaniment."""

from __future__ import annotations

import json

import musicpy as mp

from core.roles.base import Role, RoleContext


class HarmonistRole(Role):
    name = "harmonist"
    max_iterations = 2

    def run(self, piece: mp.P, context: RoleContext, llm) -> tuple[mp.P, dict]:
        """Generate accompaniment. Max 2 iterations."""
        from core.prompt_loader import load_prompt
        from core.roles.utils import extract_json
        from langchain_core.messages import SystemMessage, HumanMessage
        from core.music_transform import piece_to_json
        from agent.tool_registry import set_piece_context
        from tools.harmony.generate_accompaniment import GenerateAccompanimentTool

        template = load_prompt("harmonist")
        set_piece_context(piece)
        report = {"actions": [], "notes_added": 0}

        harmony = context.analyst_report.get('harmony', []) if context.analyst_report else []
        if not harmony:
            print("[Harmonist] No harmony data available, skipping.")
            return piece, report

        music_json = piece_to_json(piece)
        plan = context.plan or {}
        harm_params = plan.get("params", {}).get("harmonist", {})

        prompt = template.format(
            music_json=json.dumps(music_json, indent=2, ensure_ascii=False),
            analyst_report=json.dumps(context.analyst_report, indent=2, ensure_ascii=False),
            plan=json.dumps(plan, indent=2, ensure_ascii=False),
            critic_issues=json.dumps(context.critic_issues, indent=2) if context.critic_issues else "(none)",
        )

        try:
            response = llm.invoke([
                SystemMessage(content="You are a harmonist. Output ONLY JSON."),
                HumanMessage(content=prompt),
            ])
            cmd = extract_json(getattr(response, 'content', ''))
            if cmd and not cmd.get('done', False):
                style = cmd.get('style', harm_params.get('style', 'classical'))
                pattern = cmd.get('pattern', harm_params.get('pattern', 'broken_chord'))
                accompaniment = GenerateAccompanimentTool().run(
                    harmony, style=style, pattern=pattern,
                )
                new_piece = mp.P(
                    tracks=[*piece.tracks, accompaniment],
                    instruments=[*piece.instruments, 1],
                    start_times=[*piece.start_times, 0],
                    bpm=piece.bpm if piece.bpm else 120,
                )
                report["notes_added"] = len(accompaniment) if hasattr(accompaniment, '__len__') else 0
                report["actions"].append(cmd)
                set_piece_context(new_piece)
                return new_piece, report
        except Exception as e:
            print(f"[Harmonist] LLM unavailable: {e}")

        # Fallback: generate with defaults
        style = harm_params.get('style', 'classical')
        pattern = harm_params.get('pattern', 'broken_chord')
        accompaniment = GenerateAccompanimentTool().run(
            harmony, style=style, pattern=pattern,
        )
        new_piece = mp.P(
            tracks=[*piece.tracks, accompaniment],
            instruments=[*piece.instruments, 1],
            start_times=[*piece.start_times, 0],
            bpm=piece.bpm if piece.bpm else 120,
        )
        report["notes_added"] = len(accompaniment) if hasattr(accompaniment, '__len__') else 0
        set_piece_context(new_piece)
        return new_piece, report
```

- [ ] **Step 5: Write `core/roles/expression_role.py`**

```python
"""Expression role — add velocity, timing, pedal."""

from __future__ import annotations

import json

import musicpy as mp

from core.roles.base import Role, RoleContext


class ExpressionRole(Role):
    name = "expression"
    max_iterations = 2

    def run(self, piece: mp.P, context: RoleContext, llm) -> tuple[mp.P, dict]:
        """Add musical expression. Max 2 iterations."""
        from core.prompt_loader import load_prompt
        from core.roles.utils import extract_json
        from langchain_core.messages import SystemMessage, HumanMessage
        from core.music_transform import piece_to_json
        from agent.tool_registry import set_piece_context

        template = load_prompt("expression")
        set_piece_context(piece)
        iteration = 0
        used_actions = set()
        report = {"actions": [], "velocity_changes": 0, "pedal_events": 0, "timing_applied": None}

        while iteration < self.max_iterations:
            iteration += 1
            music_json = piece_to_json(piece)
            critic_issues = json.dumps(context.critic_issues, indent=2) if context.critic_issues else "(none)"

            prompt = template.format(
                music_json=json.dumps(music_json, indent=2, ensure_ascii=False),
                arrangement_report=json.dumps(context.arrangement_report, indent=2, ensure_ascii=False) if context.arrangement_report else "(none)",
                harmony_report=json.dumps(context.harmony_report, indent=2, ensure_ascii=False) if context.harmony_report else "(none)",
                critic_issues=critic_issues,
            )

            response = llm.invoke([
                SystemMessage(content="You are an expression engineer. Output ONLY JSON."),
                HumanMessage(content=prompt),
            ])

            cmd = extract_json(getattr(response, 'content', ''))
            if not cmd or cmd.get('done', False):
                break

            action_key = cmd.get('action', '')
            if action_key in used_actions:
                break
            used_actions.add(action_key)

            print(f"  [Expression iter {iteration}] Executing: {json.dumps(cmd)}")
            piece = _execute_expression(piece, cmd, context)
            set_piece_context(piece)
            report["actions"].append(cmd)

        context.expression_report = report
        print(f"\n[Expression] Done: {report}")
        return piece, report


def _execute_expression(piece: mp.P, cmd: dict, context: RoleContext) -> mp.P:
    """Execute an expression action."""
    action = cmd.get('action', '')

    if action == 'adjust_velocity':
        from tools.expression.adjust_velocity import AdjustVelocityTool
        voice_roles = context.analyst_report.get('voice_roles', {}) if context.analyst_report else None
        return AdjustVelocityTool().run(
            piece,
            voice_roles=voice_roles,
            melody_boost=cmd.get('melody_boost', 10),
            accompaniment_reduce=cmd.get('accompaniment_reduce', 10),
        )

    elif action == 'apply_timing_variation':
        from tools.expression.timing_variation import ApplyTimingVariationTool
        return ApplyTimingVariationTool().run(
            piece,
            type=cmd.get('type', 'rubato'),
            amount=cmd.get('amount', 0.05),
        )

    elif action == 'add_sustain_pedal':
        from tools.expression.add_pedal import AddSustainPedalTool
        return AddSustainPedalTool().run(piece, mode=cmd.get('mode', 'harmonic_change'))

    return piece
```

- [ ] **Step 6: Write `core/roles/critic_role.py`**

```python
"""Critic role — quality review and bounce-back."""

from __future__ import annotations

import json

import musicpy as mp

from core.roles.base import Role, RoleContext


class CriticRole(Role):
    name = "critic"
    max_iterations = 1

    def run(self, piece: mp.P, context: RoleContext, llm) -> tuple[mp.P, dict]:
        """Review piece and all reports. Returns {passed, issues}."""
        from core.prompt_loader import load_prompt
        from core.roles.utils import extract_json
        from langchain_core.messages import SystemMessage, HumanMessage
        from core.music_transform import piece_to_json

        template = load_prompt("critic")
        music_json = piece_to_json(piece)

        prompt = template.format(
            music_json=json.dumps(music_json, indent=2, ensure_ascii=False),
            analyst_report=json.dumps(context.analyst_report, indent=2, ensure_ascii=False) if context.analyst_report else "(none)",
            arrangement_report=json.dumps(context.arrangement_report, indent=2, ensure_ascii=False) if context.arrangement_report else "(none)",
            harmony_report=json.dumps(context.harmony_report, indent=2, ensure_ascii=False) if context.harmony_report else "(none)",
            expression_report=json.dumps(context.expression_report, indent=2, ensure_ascii=False) if context.expression_report else "(none)",
        )

        response = llm.invoke([
            SystemMessage(content="You are a quality reviewer. Output ONLY JSON."),
            HumanMessage(content=prompt),
        ])

        raw = getattr(response, 'content', '')
        report = extract_json(raw, {"passed": True, "issues": []})

        print(f"\n[Critic] Report: {json.dumps(report, indent=2, ensure_ascii=False)}")
        return piece, report
```

- [ ] **Step 7: Update `core/roles/__init__.py`**

```python
from core.roles.base import Role, RoleContext
from core.roles.utils import extract_json
from core.roles.planner_role import PlannerRole
from core.roles.analyst_role import AnalystRole
from core.roles.arranger_role import ArrangerRole
from core.roles.harmonist_role import HarmonistRole
from core.roles.expression_role import ExpressionRole
from core.roles.critic_role import CriticRole

__all__ = [
    "Role", "RoleContext", "extract_json",
    "PlannerRole", "AnalystRole", "ArrangerRole",
    "HarmonistRole", "ExpressionRole", "CriticRole",
]
```

- [ ] **Step 8: Commit**

```bash
git add core/roles/base.py core/roles/utils.py core/roles/__init__.py core/roles/planner_role.py core/roles/analyst_role.py core/roles/arranger_role.py core/roles/harmonist_role.py core/roles/expression_role.py core/roles/critic_role.py
git commit -m "feat: implement 6 role modules with LLM integration"
```

---

### Task 6: Rewrite orchestrator as RoleOrchestrator

**Files:**
- Modify: `core/orchestrator.py`

- [ ] **Step 1: Rewrite entire `core/orchestrator.py`**

```python
"""
Role Orchestrator — multi-role collaboration pipeline.

Manages phase transitions between Planner, Analyst, Arranger,
Harmonist, Expression, and Critic roles. Handles Critic bounce-back
(max 2 retries per role).
"""

from __future__ import annotations

import json
import os

import musicpy as mp

from core.music_io import load_midi, save_midi
from core.roles.base import RoleContext
from core.roles.analyst_role import AnalystRole
from core.roles.planner_role import PlannerRole
from core.roles.arranger_role import ArrangerRole
from core.roles.harmonist_role import HarmonistRole
from core.roles.expression_role import ExpressionRole
from core.roles.critic_role import CriticRole
from agent.tool_registry import set_piece_context, get_piece_context

MAX_BOUNCES = 2


class RoleOrchestrator:
    """Orchestrate multi-role music processing pipeline."""

    def __init__(self, llm):
        self.llm = llm

    def run(self, piece: mp.P, instruction: str) -> mp.P:
        """Run the full pipeline."""
        context = RoleContext(instruction)

        # Phase 1: Pre-analysis (tools only, no LLM)
        print("\n=== Phase 1: Pre-Analysis ===")
        analyst = AnalystRole()
        piece, _ = analyst.run_tools_only(piece, context)

        # Phase 2: Planning
        print("\n=== Phase 2: Planning ===")
        planner = PlannerRole()
        piece, plan = planner.run(piece, context, self.llm)

        phases = plan.get("phases", [])
        params = plan.get("params", {})

        # Phase 3: Execute planned phases
        for phase in phases:
            if phase == "analysis":
                # Re-run full analysis with LLM summary
                print(f"\n=== Phase: Analysis ===")
                piece, _ = analyst.run(piece, context, self.llm)

            elif phase == "arrangement":
                print(f"\n=== Phase: Arrangement ===")
                arranger = ArrangerRole()
                piece, _ = self._with_bounce_back(piece, context, arranger, "arrangement")

            elif phase == "harmonist":
                print(f"\n=== Phase: Harmonist ===")
                harmonist = HarmonistRole()
                piece, report = harmonist.run(piece, context, self.llm)
                context.harmony_report = report

            elif phase == "expression":
                print(f"\n=== Phase: Expression ===")
                expression = ExpressionRole()
                piece, _ = self._with_bounce_back(piece, context, expression, "expression")

        # Phase 4: Critic review
        print("\n=== Phase: Critic Review ===")
        critic = CriticRole()
        piece, critic_report = critic.run(piece, context, self.llm)

        # Handle bounce-back
        if not critic_report.get("passed", True) and critic_report.get("issues"):
            high_issues = [i for i in critic_report["issues"] if i.get("severity") == "high"]
            if high_issues:
                print(f"\n[Critic] {len(high_issues)} high-severity issue(s) found, bouncing back")
                # Group issues by role and bounce back
                roles_with_issues = set(i.get("role", "") for i in high_issues)
                for role_name in roles_with_issues:
                    context.critic_issues = [i for i in high_issues if i.get("role") == role_name]
                    piece = self._bounce_back(piece, context, role_name)

        return piece

    def _with_bounce_back(self, piece: mp.P, context: RoleContext,
                          role, role_key: str) -> tuple[mp.P, dict]:
        """Run a role with bounce-back support."""
        bounce_count = 0
        while bounce_count <= MAX_BOUNCES:
            piece, report = role.run(piece, context, self.llm)
            if bounce_count >= MAX_BOUNCES:
                break
            # Check if critic wants bounce back (from previous Critic run)
            if not context.critic_issues:
                break
            role_issues = [i for i in context.critic_issues if i.get("role") == role_key]
            if not role_issues:
                break
            bounce_count += 1
        return piece, report

    def _bounce_back(self, piece: mp.P, context: RoleContext, role_name: str) -> mp.P:
        """Bounce back to a specific role for rework."""
        if role_name == "arranger":
            arranger = ArrangerRole()
            piece, _ = arranger.run(piece, context, self.llm)
        elif role_name == "harmonist":
            harmonist = HarmonistRole()
            piece, _ = harmonist.run(piece, context, self.llm)
        elif role_name == "expression":
            expression = ExpressionRole()
            piece, _ = expression.run(piece, context, self.llm)
        return piece


# ── Backward compatibility ──────────────────────────────────────────


def create_music_agent(llm):
    """Deprecated: use RoleOrchestrator instead."""
    import warnings
    warnings.warn("create_music_agent is deprecated. Use RoleOrchestrator.", DeprecationWarning)

    orchestrator = RoleOrchestrator(llm)

    def agent_fn(piece, instruction: str):
        result_piece = orchestrator.run(piece, instruction)
        set_piece_context(result_piece)
        return []

    return agent_fn


def run_pipeline(midi_path: str, instruction: str, llm,
                 output_path: str = None) -> str:
    """Run the full Music Agent pipeline with multi-role orchestration."""
    piece = load_midi(midi_path)
    set_piece_context(piece)

    orchestrator = RoleOrchestrator(llm)
    result_piece = orchestrator.run(piece, instruction)

    if output_path is None:
        base, ext = os.path.splitext(midi_path)
        output_path = f"{base}_arranged{ext}"

    save_midi(result_piece, output_path)
    return output_path
```

- [ ] **Step 2: Commit**

```bash
git add core/orchestrator.py
git commit -m "feat: rewrite orchestrator as RoleOrchestrator with multi-role pipeline"
```

---

### Task 7: Wire into main.py and audio import

**Files:**
- Read: `main.py` — check current import and usage of `run_pipeline`
- Read: `core/audio_import.py` — check where orchestrator is called

We need to ensure `main.py` uses the new `run_pipeline` seamlessly. Since the function signature is preserved, this should be a drop-in replacement.

- [ ] **Step 1: Check main.py for orchestrator imports**

Check what imports `core/orchestrator` or `create_music_agent` / `run_pipeline`.

- [ ] **Step 2: Verify no breaking changes**

The new `run_pipeline(midi_path, instruction, llm, output_path)` has the same signature. `create_music_agent` is deprecated but still functional. No changes to main.py needed.

- [ ] **Step 3: Commit (no changes if drop-in compatible, or commit main.py updates if needed)**

```bash
git add main.py  # if changed
git commit -m "chore: wire RoleOrchestrator into main.py"  # if changed
```

---

### Task 8: Verification

- [ ] **Step 1: Run import check**

```bash
python -c "from core.orchestrator import RoleOrchestrator, run_pipeline; print('OK')"
```

Expected: `OK`

- [ ] **Step 2: Run role import check**

```bash
python -c "from core.roles import PlannerRole, AnalystRole, ArrangerRole, HarmonistRole, ExpressionRole, CriticRole; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Run existing tests**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | head -80
```

- [ ] **Step 4: Commit if tests pass**

```bash
git commit --allow-empty -m "chore: verify multi-role pipeline imports and tests"
```
