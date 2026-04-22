"""
MIDI ↔ ABC notation conversion using midi2abc / abc2midi CLI tools.

These are installed via Homebrew: brew install abcmidi abcm2ps
"""

import os
import subprocess


def midi_to_abc(midi_path: str, abc_path: str) -> str | None:
    """
    Convert MIDI file to ABC notation via midi2abc.

    Args:
        midi_path: Input MIDI file.
        abc_path: Output ABC file path.

    Returns:
        Path to ABC file, or None on failure.
    """
    tool = _find_tool("midi2abc")
    if not tool:
        print("  Error: midi2abc not found. Install: brew install abcmidi")
        return None

    result = subprocess.run(
        [tool, midi_path, "-o", abc_path],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0 or not os.path.exists(abc_path):
        print(f"  Error: midi2abc failed: {result.stderr.strip()}")
        return None

    return abc_path


def abc_to_midi(abc_path: str, midi_path: str) -> str | None:
    """
    Convert ABC notation to MIDI file via abc2midi.

    Args:
        abc_path: Input ABC file.
        midi_path: Output MIDI file path.

    Returns:
        Path to MIDI file, or None on failure.
    """
    tool = _find_tool("abc2midi")
    if not tool:
        print("  Error: abc2midi not found. Install: brew install abcmidi")
        return None

    result = subprocess.run(
        [tool, abc_path, "-o", midi_path],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0 or not os.path.exists(midi_path):
        print(f"  Error: abc2midi failed: {result.stderr.strip()}")
        return None

    return midi_path


def abc_to_png(abc_path: str, png_path: str) -> str | None:
    """
    Convert ABC notation to sheet music PNG via abcm2ps.

    Args:
        abc_path: Input ABC file.
        png_path: Output PNG file path.

    Returns:
        Path to PNG file, or None on failure.
    """
    tool = _find_tool("abcm2ps")
    if not tool:
        print("  Error: abcm2ps not found. Install: brew install abcm2ps")
        return None

    # abcm2ps outputs .ps files, we need to convert to PNG
    ps_dir = os.path.dirname(png_path) or "."
    ps_base = os.path.splitext(os.path.basename(png_path))[0]
    ps_output = os.path.join(ps_dir, f"{ps_base}.ps")

    result = subprocess.run(
        [tool, abc_path, "-O", ps_output],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0 or not os.path.exists(ps_output):
        print(f"  Error: abcm2ps failed: {result.stderr.strip()}")
        return None

    # Convert PS → PNG via ghostscript or sips
    gs = _find_tool("gs")
    if gs:
        subprocess.run(
            [gs, "-dSAFER", "-dBATCH", "-dNOPAUSE", "-r150",
             "-sDEVICE=png16m", f"-sOutputFile={png_path}", ps_output],
            capture_output=True, timeout=30,
        )
    else:
        sips = _find_tool("sips")
        if sips:
            subprocess.run(
                [sips, "-s", "format", "png", ps_output, "--out", png_path],
                capture_output=True, timeout=30,
            )
        else:
            print("  Warning: no PS→PNG converter found (gs or sips)")
            return None

    if os.path.exists(png_path):
        return png_path
    return None


def read_abc(path: str) -> str | None:
    """Read ABC file contents as string."""
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return f.read()


def write_abc(text: str, path: str) -> str | None:
    """Write ABC notation string to file."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    return path if os.path.exists(path) else None


def _find_tool(name: str) -> str | None:
    """Find a CLI tool in PATH."""
    for d in os.environ.get("PATH", "").split(os.pathsep):
        p = os.path.join(d, name)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None
