"""
Orchestrator — LLM deep participation loop.

The LLM sees structured JSON of the music, chooses actions, receives
feedback JSON after each action, and loops until satisfied.
"""

import json
import os
import re

from core.music_io import load_midi, save_midi
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

# Available actions for the LLM prompt
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

        # Set piece into global context so execute_command can access it
        set_piece_context(piece)

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
                # Fallback: if LLM doesn't return valid JSON, stop loop
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
