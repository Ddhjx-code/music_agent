"""
Music Agent CLI entry point.

Usage:
    python main.py input.mid "改成古典钢琴"
    python main.py input.mid "改成浪漫钢琴"
    python main.py input.mid "改成流行钢琴"
    python main.py input.mid "改成弦乐四重奏" --format wav
    python main.py input.mid "改成管乐团合奏" --format wav --sf2 /path/to.sf2
    python main.py input.wav "改成钢琴演奏" --format wav
    python main.py input.mp3 "改成钢琴演奏" --format wav
"""

import argparse
import os
import sys

from core.music_io import load_midi, save_midi
from core.json_schema import generate_summary
from core.audio_render import render_audio, discover_soundfont
from tools.arrangement.arrange_piano import ArrangePianoTool
from tools.validation.range_check import RangeCheckTool


AUDIO_EXTENSIONS = {'.wav', '.mp3', '.flac', '.ogg'}
MIDI_EXTENSIONS = {'.mid', '.midi'}


def is_audio_input(path: str) -> bool:
    """Check if input is an audio file (not MIDI)."""
    ext = os.path.splitext(path)[1].lower()
    return ext in AUDIO_EXTENSIONS


def import_audio_to_midi(audio_path: str, output_dir: str, melody_extract: bool = False) -> str | None:
    """
    Import audio file to MIDI using the full pipeline:
    Demucs stems -> per-stem transcription -> merge -> postprocess.
    """
    from core.audio_import import (
        separate_stems, wav_to_midi_basic_pitch,
        merge_midi_files, audio_to_wav,
    )
    from core.audio_postprocess import postprocess_midi
    import musicpy as mp

    print(f"Importing audio: {audio_path}")

    # Step 1: Convert to WAV
    tmp_dir = os.path.join(output_dir, 'audio_import')
    os.makedirs(tmp_dir, exist_ok=True)
    wav_path = os.path.join(tmp_dir, 'converted.wav')
    wav_result = audio_to_wav(audio_path, wav_path)
    if not wav_result:
        print("  Error: Audio conversion to WAV failed.")
        return None

    # Step 2: Stem separation
    stem_dir = os.path.join(tmp_dir, 'stems')
    os.makedirs(stem_dir, exist_ok=True)
    print("  Separating stems (Demucs)...")
    stems = separate_stems(wav_result, stem_dir)
    if not stems:
        print("  Stem separation unavailable, using full audio")
        stems = [wav_result]

    # Step 3: Transcribe each stem
    midi_dir = os.path.join(tmp_dir, 'midi')
    os.makedirs(midi_dir, exist_ok=True)
    midi_files = []
    stem_names = ['vocals', 'bass', 'drums', 'other']
    for i, stem_path in enumerate(stems):
        if isinstance(stem_path, str) and os.path.exists(stem_path):
            name = stem_names[i] if i < len(stem_names) else f'stem_{i}'
            midi_path = os.path.join(midi_dir, f'{name}.mid')
            print(f"  Transcribing: {name}...")
            result = wav_to_midi_basic_pitch(stem_path, midi_path)
            if result:
                midi_files.append((name, result))
        else:
            pass

    # Also handle case where stem is just a single file (no separation)
    if not midi_files and len(stems) == 1 and isinstance(stems[0], str):
        midi_path = os.path.join(midi_dir, 'full.mid')
        result = wav_to_midi_basic_pitch(stems[0], midi_path)
        if result:
            midi_files.append(('full', result))

    if not midi_files:
        print("  Error: No stems transcribed successfully.")
        return None

    print(f"  Transcribed {len(midi_files)} stem(s)")

    # Step 4: Merge
    merged_path = os.path.join(output_dir, 'imported.mid')
    merged = merge_midi_files(midi_files, merged_path)
    if not merged:
        print("  Error: MIDI merge failed.")
        return None

    # Step 5: Post-process
    piece = mp.read(merged)
    if melody_extract:
        from core.audio_postprocess import extract_melody_pipeline
        piece, info = extract_melody_pipeline(piece, return_info=True)
        print(f"  Enhanced melody extraction: key={info.get('key', 'unknown')}, "
              f"BPM={info.get('bpm', 120)}, notes={info.get('notes_after_split_melody', '?')}")
    else:
        piece = postprocess_midi(piece)
    mp.write(piece, name=merged)
    print(f"  MIDI: {merged} ({os.path.getsize(merged)} bytes)")

    return merged


def _build_transcription_summary(piece) -> dict:
    """Build a summary from audio transcription using musicpy built-in algorithms.

    Instead of custom melody simplifier / chord framework extractors,
    we use musicpy's:
    - mp.alg.split_melody() to extract melody from 'other' stem
    - mp.alg.chord_analysis() to detect chords
    - mp.alg.detect_scale() to find the key/scale
    """
    import musicpy as mp

    # Track mapping: vocals(0), bass(1), drums(2), other(3)
    tracks = piece.tracks
    if len(tracks) < 4:
        return {'source': 'audio_transcription', 'error': 'expected 4 stems'}

    other_track = tracks[3]
    bass_track = tracks[1]

    # 1. Extract melody using musicpy's built-in algorithm
    melody = mp.alg.split_melody(other_track, mode='chord')
    print(f"    musicpy.split_melody: {len(melody)} notes extracted")

    # 2. Detect scale from melody
    try:
        scale_result = mp.alg.detect_scale(melody)
        print(f"    musicpy.detect_scale: {scale_result}")
    except Exception:
        scale_result = 'unknown'

    # 3. Chord analysis using musicpy
    try:
        chords = mp.alg.chord_analysis(bass_track)
        chord_list = [str(c)[:60] for c in chords[:16]]
        print(f"    musicpy.chord_analysis: {len(chords)} chords detected")
        for c in chord_list[:8]:
            print(f"      {c}")
        if len(chord_list) > 8:
            print(f"      ... and {len(chord_list) - 8} more")
    except Exception:
        chords = []
        chord_list = []

    transcription_info = {
        'melody_notes': len(melody),
        'scale': str(scale_result),
        'chords_detected': len(chords),
        'chord_list': chord_list,
        'original_bpm': piece.bpm,
        'source': 'audio_transcription',
    }

    return transcription_info


def main():
    parser = argparse.ArgumentParser(description='Music Agent - MIDI arrangement tool')
    parser.add_argument('input', help='Input file path (MIDI or audio: WAV, MP3, FLAC, OGG)')
    parser.add_argument('instruction', help='Natural language instruction (e.g., "改成古典钢琴")')
    parser.add_argument('--output', '-o', help='Output file path')
    parser.add_argument('--format', '-f', choices=['mid', 'wav', 'mp3'], default='mid',
                        help='Output format: mid (default), wav, or mp3')
    parser.add_argument('--sf2', help='Custom SoundFont (.sf2) file path')
    parser.add_argument('--algo', action='store_true',
                        help='Use algorithm-only mode (no LLM)')
    parser.add_argument('--no-separate', action='store_true',
                        help='Skip stem separation for audio input (use full audio)')
    parser.add_argument('--melody-extract', action='store_true',
                        help='Use enhanced melody extraction (musicpy built-ins) for audio input')
    args = parser.parse_args()

    # Validate input
    if not os.path.exists(args.input):
        print(f"Error: File not found: {args.input}")
        sys.exit(1)

    # Validate SoundFont if provided
    if args.sf2 and not os.path.isfile(args.sf2):
        print(f"Error: SoundFont not found: {args.sf2}")
        sys.exit(1)

    # Determine output path and format
    fmt = args.format
    if args.output:
        output_path = args.output
    else:
        base, _ = os.path.splitext(args.input)
        ext_map = {'mid': '.mid', 'wav': '.wav', 'mp3': '.mp3'}
        output_path = f"{base}_arranged{ext_map.get(fmt, '.mid')}"

    # Infer format from output extension if it differs
    _, out_ext = os.path.splitext(output_path)
    if out_ext == '.wav':
        fmt = 'wav'
    elif out_ext == '.mp3':
        fmt = 'mp3'
    elif out_ext in ('.mid', '.midi'):
        fmt = 'mid'

    # Step 1: Handle audio input (WAV/MP3/FLAC/OGG) -> MIDI
    if is_audio_input(args.input):
        print(f"Audio input detected: {args.input}")
        print(f"Instruction: {args.instruction}")
        print(f"Output format: {fmt}")
        print(f"Output: {output_path}")
        print()

        midi_path = import_audio_to_midi(args.input, os.path.dirname(output_path) or '.',
                                         melody_extract=getattr(args, 'melody_extract', False))
        if not midi_path:
            print("Error: Audio import failed.")
            sys.exit(1)

        piece = load_midi(midi_path)

        # Build transcription summary using musicpy built-in algorithms
        transcription_info = _build_transcription_summary(piece)
        print(f"  Transcription summary built with musicpy algorithms")
    else:
        # MIDI input
        print(f"Input:    {args.input}")
        print(f"Instruction: {args.instruction}")
        print(f"Format:   {fmt}")
        print(f"Output:   {output_path}")
        if args.sf2:
            print(f"SF2:      {args.sf2}")
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

    # Enrich summary with transcription info if available (from audio input)
    if 'transcription_info' in dir():
        summary['source'] = 'audio_transcription'
        summary['transcription'] = transcription_info
        print(f"\n  Transcription info (musicpy analysis) - passing to LLM")

    if args.algo:
        _run_algorithm(piece, args.instruction, output_path, fmt, args.sf2)
    else:
        _run_llm_pipeline(piece, args.instruction, output_path, fmt, args.sf2,
                         summary=summary)


def _run_algorithm(piece, instruction: str, output_path: str, fmt: str, sf2: str | None = None):
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
    _save_and_validate(arranged, output_path, fmt, sf2)


def _run_llm_pipeline(piece, instruction: str, output_path: str, fmt: str, sf2: str | None = None,
                     summary: dict = None):
    """LLM-driven arrangement with tool calling via JSON commands.

    LLM sees: JSON summary (not raw note data)
    LLM decides: which tools to call, with what parameters
    musicpy executes: precise music operations
    """
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
        _run_algorithm(piece, instruction, output_path, fmt, sf2)
        return

    # Set piece context for tools
    set_piece_context(piece)

    # Invoke LLM agent with enriched summary
    enriched_summary = summary or generate_summary(piece)

    print(f"\nInvoking LLM agent...")
    print(f"\n  LLM Input (summary + instruction):")
    print(f"    Title: {enriched_summary['title']}")
    print(f"    Key: {enriched_summary['key']}, BPM: {enriched_summary['bpm']}")
    print(f"    Tracks: {enriched_summary['num_tracks']}, Measures: {enriched_summary['num_measures']}")
    print(f"    Chords: {enriched_summary['chord_progression'][:4]}")
    if 'transcription' in enriched_summary:
        print(f"    Source: audio transcription (musicpy analysis)")
        print(f"    Melody: {enriched_summary['transcription'].get('melody_notes', 'N/A')} notes")
        print(f"    Chords: {enriched_summary['transcription'].get('chords_detected', 'N/A')} detected")
    print(f"    Request: {instruction}")
    print()

    # Use orchestrator's agent (piece already loaded via set_piece_context)
    from core.orchestrator import create_music_agent

    agent = create_music_agent(llm)
    results = agent(enriched_summary, instruction)

    # Get the arranged piece from context
    from agent.tool_registry import get_piece_context
    arranged = get_piece_context() or piece
    _save_and_validate(arranged, output_path, fmt, sf2)


def _save_and_validate(arranged, output_path: str, fmt: str, sf2: str | None = None):
    """Save MIDI and optionally render to audio."""
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

    # Save MIDI (always)
    midi_path = output_path if fmt == 'mid' else output_path.rsplit('.', 1)[0] + '.mid'
    save_midi(arranged, midi_path)
    size = os.path.getsize(midi_path)
    print(f"\nSaved MIDI: {midi_path} ({size} bytes)")

    # Render audio if requested
    if fmt in ('wav', 'mp3'):
        print(f"\nRendering to {fmt.upper()}...")
        audio_path = render_audio(
            midi_path, output_path, sf2_path=sf2, format=fmt,
            expression=True,
            options={
                'postfx': {
                    'reverb': True,
                    'compression': True,
                    'normalize': True,
                    'target_db': '-14.0',
                }
            }
        )
        if audio_path and os.path.exists(audio_path):
            size = os.path.getsize(audio_path)
            print(f"  {fmt.upper()}: {audio_path} ({size} bytes)")


if __name__ == '__main__':
    main()
