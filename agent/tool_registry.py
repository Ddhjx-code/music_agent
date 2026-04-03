"""
Tool registry for LangChain agent.

Wraps music editing tools as LangChain BaseTool instances
so the LLM can discover and call them by name and description.

Tools accept string parameters (file paths, style names) so the LLM
can actually call them. The tool implementation loads the piece
internally.
"""

from langchain_core.tools import BaseTool

from tools.analysis.extract_melody import ExtractMelodyTool as _ExtractMelodyTool
from tools.analysis.analyze_harmony import AnalyzeHarmonyTool as _AnalyzeHarmonyTool
from tools.harmony.generate_accompaniment import GenerateAccompanimentTool as _GenerateAccompanimentTool
from tools.arrangement.arrange_piano import ArrangePianoTool as _ArrangePianoTool
from tools.validation.range_check import RangeCheckTool as _RangeCheckTool


# Global piece context — set by the orchestrator before agent invocation
_piece_context = None


def set_piece_context(piece):
    """Set the current piece context for tool calls."""
    global _piece_context
    _piece_context = piece


def get_piece_context():
    """Get the current piece context."""
    return _piece_context


def _format_result(result) -> str:
    """Format a tool result as a string for the LLM."""
    if isinstance(result, dict):
        if 'passed' in result:
            status = "PASSED" if result['passed'] else f"FAILED ({len(result.get('issues', []))} issues)"
            return f"Validation: {status}"
        return str(result)
    if hasattr(result, 'tracks'):
        return (
            f"Piece with {len(result.tracks)} tracks, "
            f"BPM={getattr(result, 'bpm', '?')}, "
            f"notes={[len(t) for t in result.tracks]}"
        )
    if hasattr(result, '__len__'):
        return f"Result with {len(result)} items"
    return str(result)


class ArrangeForPianoTool(BaseTool):
    """LangChain tool: arrange the current piece for piano."""
    name: str = "arrange_for_piano"
    description: str = (
        "Arrange the current piece for piano solo (right hand melody + left hand accompaniment). "
        "Args: style (str) - 'classical', 'romantic', or 'pop'. "
        "Returns a 2-track piece within piano range."
    )

    def _run(self, style: str = "classical") -> str:
        piece = get_piece_context()
        if piece is None:
            return "Error: No piece loaded. Please load a MIDI file first."
        tool = _ArrangePianoTool()
        result = tool.run(piece, style=style)
        # Update the piece context with the arranged result
        set_piece_context(result)
        return _format_result(result)


class ExtractMelodyTool(BaseTool):
    """LangChain tool: extract melody from the current piece."""
    name: str = "extract_melody"
    description: str = (
        "Extract the primary melody from the current piece. "
        "Returns the melody notes."
    )

    def _run(self) -> str:
        piece = get_piece_context()
        if piece is None:
            return "Error: No piece loaded."
        tool = _ExtractMelodyTool()
        result = tool.run(piece)
        return _format_result(result)


class AnalyzeHarmonyTool(BaseTool):
    """LangChain tool: analyze harmony of the current piece."""
    name: str = "analyze_harmony"
    description: str = (
        "Analyze the chord progression of the current piece. "
        "Returns list of {measure, chord} dicts."
    )

    def _run(self) -> str:
        piece = get_piece_context()
        if piece is None:
            return "Error: No piece loaded."
        tool = _AnalyzeHarmonyTool()
        result = tool.run(piece)
        return _format_result(result)


class GenerateAccompanimentTool(BaseTool):
    """LangChain tool: generate accompaniment from the current piece's harmony."""
    name: str = "generate_accompaniment"
    description: str = (
        "Generate piano accompaniment from the current piece's chord progression. "
        "Args: style (str) - 'classical', 'romantic', or 'pop'. "
        "Returns accompaniment notes."
    )

    def _run(self, style: str = "classical") -> str:
        piece = get_piece_context()
        if piece is None:
            return "Error: No piece loaded."
        harmony_tool = _AnalyzeHarmonyTool()
        harmony = harmony_tool.run(piece)
        accomp_tool = _GenerateAccompanimentTool()
        pattern_map = {
            'classical': 'broken_chord',
            'romantic': 'arpeggio',
            'pop': 'block_chord',
        }
        result = accomp_tool.run(
            harmony, style=style,
            pattern=pattern_map.get(style, 'broken_chord'),
        )
        return _format_result(result)


class ValidateRangeTool(BaseTool):
    """LangChain tool: validate instrument range."""
    name: str = "validate_range"
    description: str = (
        "Check that all notes are within the playable range of the target instrument. "
        "Args: instrument (str) - 'piano', 'violin', 'cello', etc. Default: 'piano'. "
        "Returns {passed: bool, issues: list}."
    )

    def _run(self, instrument: str = "piano") -> str:
        piece = get_piece_context()
        if piece is None:
            return "Error: No piece loaded."
        tool = _RangeCheckTool()
        result = tool.run(piece, instrument=instrument)
        return _format_result(result)


TOOLS = [
    ArrangeForPianoTool(),
    ExtractMelodyTool(),
    AnalyzeHarmonyTool(),
    GenerateAccompanimentTool(),
    ValidateRangeTool(),
]


def get_tool_names() -> list[str]:
    """Return list of registered tool names."""
    return [tool.name for tool in TOOLS]


def get_tool_by_name(name: str):
    """Get a tool instance by name."""
    for tool in TOOLS:
        if tool.name == name:
            return tool
    raise ValueError(f"Unknown tool: {name}")
