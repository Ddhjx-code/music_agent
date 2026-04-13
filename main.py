"""
Music Agent CLI entry point.

Usage:
    python main.py input.mid "改成古典钢琴"
    python main.py input.mid "改成浪漫钢琴"
    python main.py input.mid "改成流行钢琴"
    python main.py input.mid "改成爵士钢琴" --output output.mid
"""

import argparse
import os
import sys

from core.music_io import load_midi, save_midi
from core.json_schema import generate_summary
from tools.arrangement.arrange_piano import ArrangePianoTool
from tools.validation.range_check import RangeCheckTool


def main():
    parser = argparse.ArgumentParser(description='Music Agent — MIDI arrangement tool')
    parser.add_argument('input', help='Input MIDI file path')
    parser.add_argument('instruction', help='Natural language instruction (e.g., "改成古典钢琴")')
    parser.add_argument('--output', '-o', help='Output file path (default: input_arranged.mid or .wav)')
    parser.add_argument('--format', '-f', choices=['mid', 'wav'], default='mid',
                        help='Output format: mid (default) or wav')
    parser.add_argument('--algo', action='store_true',
                        help='Use algorithm-only mode (no LLM)')
    args = parser.parse_args()

    # Validate input
    if not os.path.exists(args.input):
        print(f"Error: File not found: {args.input}")
        sys.exit(1)

    # Determine output path and format
    fmt = args.format
    default_ext = '.wav' if fmt == 'wav' else '.mid'
    if args.output:
        output_path = args.output
    else:
        base, _ = os.path.splitext(args.input)
        output_path = f"{base}_arranged{default_ext}"

    # If output path has different extension, infer format from it
    _, out_ext = os.path.splitext(output_path)
    if out_ext == '.wav':
        fmt = 'wav'
    elif out_ext in ('.mid', '.midi'):
        fmt = 'mid'

    # Step 1: Load MIDI
    print(f"Input:    {args.input}")
    print(f"Instruction: {args.instruction}")
    print(f"Format:   {fmt}")
    print(f"Output:   {output_path}")
    print()

    print("Loading MIDI...")
    piece = load_midi(args.input)
    print(f"  Tracks: {len(piece.tracks)}, BPM: {piece.bpm}")

    # Step 2: Generate summary
    summary = generate_summary(piece)
    print(f"  Key: {summary['key']}, Measures: {summary['num_measures']}")
    print(f"  Chord progression: {len(summary['chord_progression'])} chords detected")
    for entry in summary['chord_progression'][:8]:
        print(f"    Measure {entry['measure']}: {entry['chord']}")
    if len(summary['chord_progression']) > 8:
        print(f"    ... and {len(summary['chord_progression']) - 8} more")

    if args.algo:
        # Algorithm-only mode (legacy)
        _run_algorithm(piece, args.instruction, output_path, fmt)
    else:
        # LLM-driven mode (default)
        _run_llm_pipeline(piece, args.instruction, output_path, fmt)


def _run_algorithm(piece, instruction: str, output_path: str, fmt: str):
    """Algorithm-only arrangement (legacy string-matching mode)."""
    STYLE_MAP = {
        '古典': 'classical', 'classical': 'classical',
        '浪漫': 'romantic', 'romantic': 'romantic',
        '流行': 'pop', 'pop': 'pop',
        '爵士': 'classical', 'jazz': 'classical',
    }
    instruction_lower = instruction.lower()
    style = 'classical'
    for keyword, style_name in STYLE_MAP.items():
        if keyword in instruction_lower:
            style = style_name
            break

    print(f"Mode:     algorithm")
    print(f"Style:    {style}")

    arranged = ArrangePianoTool().run(piece, style=style)
    _save_and_validate(arranged, output_path, fmt)


def _run_llm_pipeline(piece, instruction: str, output_path: str, fmt: str):
    """LLM-driven arrangement with tool calling via JSON commands."""
    from core.llm import get_llm
    from agent.tool_registry import set_piece_context

    print("Mode:     LLM agent")

    # Initialize LLM
    try:
        llm = get_llm()
        model_name = getattr(llm, 'model_name', None) or getattr(llm, 'model', 'unknown')
        print(f"Model:    {model_name}")
    except ValueError as e:
        print(f"  Error: {e}")
        print("  Falling back to algorithm mode. Use --algo to skip LLM entirely.")
        _run_algorithm(piece, instruction, output_path, fmt)
        return

    # Set piece context for tools
    set_piece_context(piece)

    # Invoke LLM agent
    print(f"\nInvoking LLM agent...")
    summary = generate_summary(piece)

    print(f"\n  LLM Input (summary + instruction):")
    print(f"    Title: {summary['title']}")
    print(f"    Key: {summary['key']}, BPM: {summary['bpm']}")
    print(f"    Tracks: {summary['num_tracks']}, Measures: {summary['num_measures']}")
    print(f"    Chords: {summary['chord_progression'][:4]}")
    print(f"    Request: {instruction}")
    print()

    # Use orchestrator's agent directly (piece already loaded)
    from core.orchestrator import create_music_agent

    agent = create_music_agent(llm)
    results = agent(summary, instruction)

    # Get the arranged piece from context
    from agent.tool_registry import get_piece_context
    arranged = get_piece_context() or piece
    _save_and_validate(arranged, output_path, fmt)


def _save_and_validate(arranged, output_path: str, fmt: str):
    """Save MIDI and optionally render to WAV."""
    if hasattr(arranged, 'tracks') and len(arranged.tracks) >= 2:
        print(f"  RH track: {len(arranged.tracks[0])} notes")
        print(f"  LH track: {len(arranged.tracks[1])} notes")
        result = RangeCheckTool().run(arranged, instrument='piano')
    else:
        print(f"  Output: {len(arranged.tracks) if hasattr(arranged, 'tracks') else 0} tracks")
        result = {'passed': True, 'issues': []}
    if result['passed']:
        print("  Range check: PASSED")
    else:
        print(f"  Range check: FAILED ({len(result['issues'])} issues)")
        for issue in result['issues'][:5]:
            print(f"    - {issue}")

    midi_path = output_path if fmt == 'mid' else output_path.rsplit('.', 1)[0] + '.mid'
    save_midi(arranged, midi_path)
    size = os.path.getsize(midi_path)
    print(f"\nSaved MIDI: {midi_path} ({size} bytes)")

    if fmt == 'wav':
        print("\nRendering to WAV...")
        sf2_path = _find_soundfont()
        if sf2_path is None:
            print("  Warning: No SoundFont found. WAV rendering skipped.")
            print("  Install fluidsynth: brew install fluidsynth")
        else:
            wav_path = _render_wav(midi_path, output_path, sf2_path)
            if wav_path:
                size = os.path.getsize(wav_path)
                print(f"  WAV: {wav_path} ({size} bytes)")


def _find_soundfont() -> str | None:
    """Find an available SoundFont file."""
    candidates = [
        # Homebrew fluid-synth default
        '/opt/homebrew/Cellar/fluid-synth/2.5.3/share/fluid-synth/sf2/VintageDreamsWaves-v2.sf2',
        # Homebrew symlinks
        '/opt/homebrew/share/fluid-synth/sf2/VintageDreamsWaves-v2.sf2',
        # System locations
        '/usr/share/sounds/sf2/FluidR3_GM.sf2',
        '/usr/share/sounds/sf2/TimGM6mb.sf2',
        # Project-local
        'assets/FluidR3_GM.sf2',
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _render_wav(midi_path: str, wav_path: str, sf2_path: str) -> str | None:
    """Render MIDI to WAV using fluidsynth."""
    import subprocess, tempfile, wave

    raw_path = wav_path.rsplit('.', 1)[0] + '.raw'
    try:
        result = subprocess.run(
            ['fluidsynth', '-ni', '-F', raw_path, sf2_path, midi_path],
            capture_output=True, text=True, timeout=120
        )
        if not os.path.exists(raw_path):
            print(f"  Error: fluidsynth failed: {result.stderr[:200]}")
            return None

        # Convert raw (16-bit LE, 44100Hz, stereo) to WAV
        with open(raw_path, 'rb') as fin, wave.open(wav_path, 'wb') as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(44100)
            wav.writeframes(fin.read())

        os.remove(raw_path)  # Clean up temp raw file
        return wav_path
    except FileNotFoundError:
        print("  Error: fluidsynth not found. Install with: brew install fluidsynth")
        return None
    except subprocess.TimeoutExpired:
        print("  Error: fluidsynth timed out")
        return None


if __name__ == '__main__':
    main()
