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
from tools.arrangement.arrange_strings import ArrangeStringsTool as _ArrangeStringsTool
from tools.arrangement.arrange_winds import ArrangeWindsTool as _ArrangeWindsTool
from tools.expression.add_pedal import AddSustainPedalTool as _AddSustainPedalTool
from tools.expression.adjust_velocity import AdjustVelocityTool as _AdjustVelocityTool
from tools.expression.timing_variation import ApplyTimingVariationTool as _ApplyTimingVariationTool
from tools.validation.theory_check import ValidateTheoryTool as _ValidateTheoryTool


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


class ArrangeForStringsTool(BaseTool):
    """LangChain tool: arrange the current piece for string quartet."""
    name: str = "arrange_for_strings"
    description: str = (
        "Arrange the current piece for string quartet (Violin 1, Violin 2, Viola, Cello). "
        "Maps melody to Vln1, harmony to Vln2, inner voice to Viola, bass to Cello. "
        "Automatically checks instrument ranges. "
        "Args: voicing (str) - 'standard' (default). "
        "Returns a 4-track piece."
    )

    def _run(self, voicing: str = "standard") -> str:
        piece = get_piece_context()
        if piece is None:
            return "Error: No piece loaded. Please load a MIDI file first."
        tool = _ArrangeStringsTool()
        result = tool.run(piece, voicing=voicing)
        set_piece_context(result)
        return _format_result(result)


class ArrangeForWindsTool(BaseTool):
    """LangChain tool: arrange the current piece for wind ensemble."""
    name: str = "arrange_for_winds"
    description: str = (
        "Arrange the current piece for wind ensemble "
        "(Flute, Clarinet in Bb, Alto Sax, Trumpet in Bb, French Horn, Trombone, Tuba). "
        "Args: instrumentation (str) - 'standard' (7 tracks) or 'quintet' (5 tracks), "
        "concert_pitch_notation (bool) - True for concert pitch (default), False for transposed notation. "
        "Returns a multi-track piece with wind instruments."
    )

    def _run(self, instrumentation: str = "standard", concert_pitch_notation: bool = True) -> str:
        piece = get_piece_context()
        if piece is None:
            return "Error: No piece loaded. Please load a MIDI file first."
        tool = _ArrangeWindsTool()
        result = tool.run(
            piece,
            instrumentation=instrumentation,
            concert_pitch_notation=concert_pitch_notation,
        )
        set_piece_context(result)
        return _format_result(result)


class AddSustainPedalTool(BaseTool):
    """LangChain tool: add sustain pedal events."""
    name: str = "add_sustain_pedal"
    description: str = (
        "Insert CC#64 sustain pedal events at harmonic change points. "
        "Args: mode (str) - 'harmonic_change' (default) or 'every_measure'. "
        "Returns the piece with pedal events."
    )

    def _run(self, mode: str = "harmonic_change") -> str:
        piece = get_piece_context()
        if piece is None:
            return "Error: No piece loaded."
        tool = _AddSustainPedalTool()
        result = tool.run(piece, mode=mode)
        set_piece_context(result)
        return _format_result(result)


class AdjustVelocityTool(BaseTool):
    """LangChain tool: adjust note velocities."""
    name: str = "adjust_velocity"
    description: str = (
        "Adjust note velocities to create dynamic contrast. "
        "Args: melody_boost (int) - increase for melody (default 0), "
        "accompaniment_reduce (int) - decrease for accompaniment (default 0). "
        "Returns the piece with adjusted velocities."
    )

    def _run(self, melody_boost: int = 0, accompaniment_reduce: int = 0) -> str:
        piece = get_piece_context()
        if piece is None:
            return "Error: No piece loaded."
        tool = _AdjustVelocityTool()
        result = tool.run(piece, melody_boost=melody_boost, accompaniment_reduce=accompaniment_reduce)
        set_piece_context(result)
        return _format_result(result)


class ApplyTimingVariationTool(BaseTool):
    """LangChain tool: apply rubato or swing timing."""
    name: str = "apply_timing_variation"
    description: str = (
        "Apply subtle timing variation for human-like performance. "
        "Args: type (str) - 'rubato' (phrase-end deceleration) or 'swing' "
        "(unequal eighth notes), amount (float) - intensity (0.01-0.2, default 0.05). "
        "Returns the piece with modified timing."
    )

    def _run(self, type: str = "rubato", amount: float = 0.05) -> str:
        piece = get_piece_context()
        if piece is None:
            return "Error: No piece loaded."
        tool = _ApplyTimingVariationTool()
        result = tool.run(piece, type=type, amount=amount)
        set_piece_context(result)
        return _format_result(result)


TOOLS = [
    ArrangeForPianoTool(),
    ExtractMelodyTool(),
    AnalyzeHarmonyTool(),
    GenerateAccompanimentTool(),
    ValidateRangeTool(),
    ArrangeForStringsTool(),
    ArrangeForWindsTool(),
    AddSustainPedalTool(),
    AdjustVelocityTool(),
    ApplyTimingVariationTool(),
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
