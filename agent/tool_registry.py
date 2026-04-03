"""
Tool registry for LangChain agent.

Registers all music editing tools with LangChain so the LLM
can discover and call them by name and description.
"""

from tools.analysis.extract_melody import ExtractMelodyTool
from tools.analysis.analyze_harmony import AnalyzeHarmonyTool
from tools.harmony.generate_accompaniment import GenerateAccompanimentTool
from tools.arrangement.arrange_piano import ArrangePianoTool
from tools.validation.range_check import RangeCheckTool


# All available tools for the LLM to orchestrate
TOOLS = [
    ExtractMelodyTool(),
    AnalyzeHarmonyTool(),
    GenerateAccompanimentTool(),
    ArrangePianoTool(),
    RangeCheckTool(),
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
