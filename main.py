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


STYLE_MAP = {
    '古典': 'classical',
    'classical': 'classical',
    '浪漫': 'romantic',
    'romantic': 'romantic',
    '流行': 'pop',
    'pop': 'pop',
    '爵士': 'classical',  # Jazz uses classical broken chord as base for now
    'jazz': 'classical',
}


def main():
    parser = argparse.ArgumentParser(description='Music Agent — MIDI arrangement tool')
    parser.add_argument('input', help='Input MIDI file path')
    parser.add_argument('instruction', help='Natural language instruction (e.g., "改成古典钢琴")')
    parser.add_argument('--output', '-o', help='Output MIDI file path (default: input_arranged.mid)')
    args = parser.parse_args()

    # Validate input
    if not os.path.exists(args.input):
        print(f"Error: File not found: {args.input}")
        sys.exit(1)

    # Parse style from instruction
    instruction_lower = args.instruction.lower()
    style = 'classical'  # default
    for keyword, style_name in STYLE_MAP.items():
        if keyword in instruction_lower:
            style = style_name
            break

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        base, ext = os.path.splitext(args.input)
        output_path = f"{base}_arranged{ext}"

    print(f"Input:    {args.input}")
    print(f"Style:    {style}")
    print(f"Output:   {output_path}")
    print()

    # Step 1: Load MIDI
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

    # Step 3: Arrange for piano
    print(f"\nArranging for piano ({style})...")
    arranged = ArrangePianoTool().run(piece, style=style)
    print(f"  RH track: {len(arranged.tracks[0])} notes")
    print(f"  LH track: {len(arranged.tracks[1])} notes")

    # Step 4: Validate range
    result = RangeCheckTool().run(arranged, instrument='piano')
    if result['passed']:
        print("  Range check: PASSED")
    else:
        print(f"  Range check: FAILED ({len(result['issues'])} issues)")
        for issue in result['issues'][:5]:
            print(f"    - {issue}")

    # Step 5: Save
    save_midi(arranged, output_path)
    size = os.path.getsize(output_path)
    print(f"\nSaved: {output_path} ({size} bytes)")


if __name__ == '__main__':
    main()
