"""Analyst role — extract melody, harmony, voice roles, range check."""

from __future__ import annotations

import json

import musicpy as mp

from core.roles.base import Role, RoleContext


class AnalystRole(Role):
    name = "analyst"
    max_iterations = 1

    def run(self, piece: mp.P, context: RoleContext, llm) -> tuple[mp.P, dict]:
        """Analyze piece and produce structured report. Does not modify piece."""
        from tools.analysis.extract_melody import ExtractMelodyTool
        from tools.analysis.analyze_harmony import AnalyzeHarmonyTool
        from tools.validation.range_check import RangeCheckTool
        from tools.analysis.voice_detection import detect_voice_roles
        from core.prompt_loader import load_prompt
        from core.roles.utils import extract_json
        from langchain_core.messages import SystemMessage, HumanMessage

        # Run analysis tools directly (no LLM needed for raw analysis)
        melody = ExtractMelodyTool().run(piece)
        harmony = AnalyzeHarmonyTool().run(piece, granularity='measure')
        voice_roles = detect_voice_roles(piece)
        range_result = RangeCheckTool().run(piece, instrument='piano')

        # Build tool analysis report
        tool_report = {
            "melody": {
                "notes_count": len(melody) if hasattr(melody, '__len__') else 0,
                "track_indices": [],
            },
            "harmony": harmony,
            "voice_roles": voice_roles,
            "range_issues": range_result.get('issues', []),
            "range_passed": range_result.get('passed', True),
        }

        context.analyst_report = tool_report
        print(f"\n[Analyst] Report: {json.dumps(tool_report, indent=2, ensure_ascii=False)[:500]}...")
        return piece, tool_report

    def run_tools_only(self, piece: mp.P, context: RoleContext) -> tuple[mp.P, dict]:
        """Run analysis tools without LLM (for pre-analysis before Planner)."""
        return self.run(piece, context, llm=None)
