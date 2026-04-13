"""
Orchestrator — the user-facing API for the Music Agent pipeline.

Wires together: MIDI I/O → music summary → LLM JSON decision → tool execution → output MIDI.

The LLM outputs JSON commands, and the orchestrator parses and executes them.
This works with any LLM that supports JSON output (including models without function calling).
"""

import json
import os
import re

from core.music_io import load_midi, save_midi
from core.json_schema import generate_summary
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
from agent.prompt_templates import SYSTEM_PROMPT


def parse_llm_response(text: str) -> dict:
    """
    Parse LLM response text to extract the JSON command.

    Handles cases where the LLM wraps JSON in markdown code blocks
    or includes extra text around it.
    """
    # Try to find JSON in markdown code block
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        return json.loads(match.group(1))

    # Try to find JSON object in text
    match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError(f"Could not parse JSON from LLM response: {text}")


def execute_command(cmd: dict) -> str:
    """
    Execute a JSON command from the LLM.

    Supported commands:
    - arrange_for_piano: {action, style}
    - analyze_harmony: {action}
    - extract_melody: {action}
    - generate_accompaniment: {action, style}
    - validate_range: {action, instrument}
    """
    action = cmd.get('action', '')
    piece = get_piece_context()

    if action == 'arrange_for_piano':
        style = cmd.get('style', 'classical')
        tool = _ArrangePianoTool()
        result = tool.run(piece, style=style)
        set_piece_context(result)
        return f"Arranged for piano ({style}): {len(result.tracks)} tracks"

    elif action == 'analyze_harmony':
        tool = _AnalyzeHarmonyTool()
        result = tool.run(piece)
        return f"Analyzed: {len(result)} chords"

    elif action == 'extract_melody':
        tool = _ExtractMelodyTool()
        result = tool.run(piece)
        return f"Extracted melody: {len(result)} notes"

    elif action == 'generate_accompaniment':
        style = cmd.get('style', 'classical')
        harmony = _AnalyzeHarmonyTool().run(piece)
        pattern_map = {
            'classical': 'broken_chord',
            'romantic': 'arpeggio',
            'pop': 'block_chord',
        }
        accomp_tool = _GenerateAccompanimentTool()
        result = accomp_tool.run(harmony, style=style, pattern=pattern_map.get(style, 'broken_chord'))
        return f"Generated accompaniment: {len(result)} notes"

    elif action == 'validate_range':
        instrument = cmd.get('instrument', 'piano')
        tool = _RangeCheckTool()
        result = tool.run(piece, instrument=instrument)
        status = "PASSED" if result['passed'] else f"FAILED ({len(result['issues'])} issues)"
        return f"Range check ({instrument}): {status}"

    elif action == 'arrange_for_strings':
        voicing = cmd.get('voicing', 'standard')
        tool = _ArrangeStringsTool()
        result = tool.run(piece, voicing=voicing)
        set_piece_context(result)
        return f"Arranged for string quartet: {len(result.tracks)} tracks"

    elif action == 'arrange_for_winds':
        instrumentation = cmd.get('instrumentation', 'standard')
        concert_pitch = cmd.get('concert_pitch_notation', True)
        tool = _ArrangeWindsTool()
        result = tool.run(piece, instrumentation=instrumentation, concert_pitch_notation=concert_pitch)
        set_piece_context(result)
        return f"Arranged for wind ensemble ({instrumentation}): {len(result.tracks)} tracks"

    elif action == 'add_sustain_pedal':
        mode = cmd.get('mode', 'harmonic_change')
        tool = _AddSustainPedalTool()
        result = tool.run(piece, mode=mode)
        set_piece_context(result)
        pedal_count = len(getattr(result, 'other_messages', []))
        return f"Added {pedal_count} pedal events ({mode})"

    elif action == 'adjust_velocity':
        melody_boost = cmd.get('melody_boost', 0)
        accomp_reduce = cmd.get('accompaniment_reduce', 0)
        tool = _AdjustVelocityTool()
        result = tool.run(piece, melody_boost=melody_boost, accompaniment_reduce=accomp_reduce)
        set_piece_context(result)
        return f"Adjusted velocity (melody +{melody_boost}, accomp -{accomp_reduce})"

    elif action == 'apply_timing_variation':
        vtype = cmd.get('type', 'rubato')
        amount = cmd.get('amount', 0.05)
        tool = _ApplyTimingVariationTool()
        result = tool.run(piece, type=vtype, amount=amount)
        set_piece_context(result)
        return f"Applied {vtype} timing variation (amount={amount})"

    else:
        return f"Unknown action: {action}"


def create_music_agent(llm):
    """
    Create a music agent that uses LLM JSON output to orchestrate tools.

    Args:
        llm: A LangChain-compatible chat model instance.

    Returns:
        A callable that takes (music_summary, instruction) and returns
        list of (command, result) tuples.
    """
    def agent_fn(music_summary: dict, instruction: str) -> list[tuple[dict, str]]:
        from langchain_core.messages import SystemMessage, HumanMessage

        prompt = (
            f"You are a music assistant. Analyze this music and fulfill the user's request.\n\n"
            f"Music summary:\n{json.dumps(music_summary, indent=2)}\n\n"
            f"User request: {instruction}\n\n"
            f"Respond with ONLY a JSON object. No markdown, no explanation.\n"
            f"Available actions:\n"
            f'- arrange_for_piano: {{"action": "arrange_for_piano", "style": "classical|romantic|pop"}}\n'
            f'- arrange_for_strings: {{"action": "arrange_for_strings", "voicing": "standard"}}\n'
            f'- arrange_for_winds: {{"action": "arrange_for_winds", "instrumentation": "standard|quintet", "concert_pitch_notation": true}}\n'
            f'- analyze_harmony: {{"action": "analyze_harmony"}}\n'
            f'- extract_melody: {{"action": "extract_melody"}}\n'
            f'- generate_accompaniment: {{"action": "generate_accompaniment", "style": "..."}}\n'
            f'- validate_range: {{"action": "validate_range", "instrument": "piano|violin|viola|cello|flute|clarinet|trumpet|trombone|tuba|french_horn|alto_sax"}}\n'
            f'- add_sustain_pedal: {{"action": "add_sustain_pedal", "mode": "harmonic_change|every_measure"}}\n'
            f'- adjust_velocity: {{"action": "adjust_velocity", "melody_boost": 10, "accompaniment_reduce": 10}}\n'
            f'- apply_timing_variation: {{"action": "apply_timing_variation", "type": "rubato|swing", "amount": 0.05}}\n'
            f'You can chain multiple actions in a list: [{{"action": "..."}}, {{"action": "..."}}]'
        )

        response = llm.invoke([
            SystemMessage(content="You are a music assistant. Respond with ONLY JSON."),
            HumanMessage(content=prompt),
        ])

        # Parse JSON from response
        text = response.content.strip()
        try:
            cmd = parse_llm_response(text)
        except (json.JSONDecodeError, ValueError):
            # Fallback to basic style detection
            style = 'classical'
            if 'romantic' in instruction.lower():
                style = 'romantic'
            elif 'pop' in instruction.lower():
                style = 'pop'
            cmd = {'action': 'arrange_for_piano', 'style': style}

        # Execute commands
        commands = cmd if isinstance(cmd, list) else [cmd]
        results = []
        for c in commands:
            print(f"  Executing: {json.dumps(c)}")
            result = execute_command(c)
            results.append((c, result))

        return results

    return agent_fn


def run_pipeline(midi_path: str, instruction: str, llm,
                 output_path: str = None) -> str:
    """
    Run the full Music Agent pipeline.

    Args:
        midi_path: Path to the input MIDI file.
        instruction: Natural language instruction.
        llm: A LangChain-compatible chat model instance.
        output_path: Optional output MIDI path.

    Returns:
        Path to the output MIDI file.
    """
    # Step 1: Load MIDI
    piece = load_midi(midi_path)
    set_piece_context(piece)

    # Step 2: Generate summary
    summary = generate_summary(piece)

    # Step 3: Create agent and get LLM decision
    agent = create_music_agent(llm)
    results = agent(summary, instruction)

    # Step 5: Get the (possibly modified) piece and save
    result_piece = get_piece_context()
    if output_path is None:
        base, ext = os.path.splitext(midi_path)
        output_path = f"{base}_arranged{ext}"

    save_midi(result_piece, output_path)
    return output_path
