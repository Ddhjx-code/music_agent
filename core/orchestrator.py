"""
Orchestrator — the user-facing API for the Music Agent pipeline.

Wires together: MIDI I/O → music summary → LLM JSON decision → tool execution → output MIDI.

The LLM outputs JSON commands (not tool calls), and the orchestrator
parses and executes them. This works with any LLM that supports JSON output.
"""

import json
import os
import re

from core.music_io import load_midi, save_midi
from core.json_schema import generate_summary
from agent.tool_registry import (
    set_piece_context, get_piece_context,
    ArrangeForPianoTool, ExtractMelodyTool,
    AnalyzeHarmonyTool, GenerateAccompanimentTool,
    ValidateRangeTool,
)
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

    if action == 'arrange_for_piano':
        style = cmd.get('style', 'classical')
        piece = get_piece_context()
        tool = ArrangeForPianoTool()
        result = tool._run(style=style)
        return result

    elif action == 'analyze_harmony':
        piece = get_piece_context()
        tool = AnalyzeHarmonyTool()
        result = tool._run()
        return result

    elif action == 'extract_melody':
        piece = get_piece_context()
        tool = ExtractMelodyTool()
        result = tool._run()
        return result

    elif action == 'generate_accompaniment':
        style = cmd.get('style', 'classical')
        piece = get_piece_context()
        tool = GenerateAccompanimentTool()
        result = tool._run(style=style)
        return result

    elif action == 'validate_range':
        instrument = cmd.get('instrument', 'piano')
        piece = get_piece_context()
        tool = ValidateRangeTool()
        result = tool._run(instrument=instrument)
        return result

    else:
        return f"Unknown action: {action}"


def create_music_agent(llm):
    """
    Create a music agent that uses LLM JSON output to orchestrate tools.

    Args:
        llm: A LangChain-compatible LLM instance.

    Returns:
        A callable that takes (music_summary, instruction) and returns output.
    """
    def agent_fn(music_summary: dict, instruction: str) -> str:
        from langchain_core.messages import SystemMessage, HumanMessage

        prompt = (
            f"You are a music assistant. Analyze this music and fulfill the user's request.\n\n"
            f"Music summary:\n{json.dumps(music_summary, indent=2)}\n\n"
            f"User request: {instruction}\n\n"
            f"Respond with ONLY a JSON object. No markdown, no explanation.\n"
            f"Available actions:\n"
            f'- arrange_for_piano: {{"action": "arrange_for_piano", "style": "classical|romantic|pop"}}\n'
            f'- analyze_harmony: {{"action": "analyze_harmony"}}\n'
            f'- extract_melody: {{"action": "extract_melody"}}\n'
            f'- generate_accompaniment: {{"action": "generate_accompaniment", "style": "..."}}\n'
            f'- validate_range: {{"action": "validate_range", "instrument": "piano"}}\n'
            f'You can chain multiple actions in a list: [{{"action": "..."}}, {{"action": "..."}}]'
        )

        response = llm.invoke([
            SystemMessage(content="You are a music assistant. Respond with ONLY JSON."),
            HumanMessage(content=prompt),
        ])

        return response.content

    return agent_fn


def run_pipeline(midi_path: str, instruction: str, llm,
                 output_path: str = None) -> str:
    """
    Run the full Music Agent pipeline.

    Args:
        midi_path: Path to the input MIDI file.
        instruction: Natural language instruction.
        llm: A LangChain-compatible LLM instance.
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
    llm_response = agent(summary, instruction)

    # Step 4: Parse and execute
    try:
        cmd = parse_llm_response(llm_response)
    except (json.JSONDecodeError, ValueError) as e:
        # Fallback: parse style from instruction directly
        style = 'classical'
        if 'romantic' in instruction.lower():
            style = 'romantic'
        elif 'pop' in instruction.lower():
            style = 'pop'
        cmd = {'action': 'arrange_for_piano', 'style': style}

    # Handle single command or list of commands
    commands = cmd if isinstance(cmd, list) else [cmd]
    results = []
    for c in commands:
        result = execute_command(c)
        results.append(result)

    # Step 5: Get the (possibly modified) piece and save
    result_piece = get_piece_context()
    if output_path is None:
        base, ext = os.path.splitext(midi_path)
        output_path = f"{base}_arranged{ext}"

    save_midi(result_piece, output_path)
    return output_path
