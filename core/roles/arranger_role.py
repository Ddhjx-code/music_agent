"""Arranger role — arrange piece for target instrumentation."""

from __future__ import annotations

import json

import musicpy as mp

from core.roles.base import Role, RoleContext


class ArrangerRole(Role):
    name = "arranger"
    max_iterations = 2

    def run(self, piece: mp.P, context: RoleContext, llm) -> tuple[mp.P, dict]:
        """Arrange piece according to plan. Max 2 iterations."""
        from core.prompt_loader import load_prompt
        from core.roles.utils import extract_json
        from langchain_core.messages import SystemMessage, HumanMessage
        from core.music_transform import piece_to_json
        from agent.tool_registry import set_piece_context

        template = load_prompt("arranger")
        set_piece_context(piece)
        iteration = 0
        used_actions = set()
        report = {"actions": [], "tracks_before": len(piece.tracks)}

        while iteration < self.max_iterations:
            iteration += 1
            music_json = piece_to_json(piece)
            critic_issues = json.dumps(context.critic_issues, indent=2) if context.critic_issues else "(none)"

            prompt = template.format(
                music_json=json.dumps(music_json, indent=2, ensure_ascii=False),
                analyst_report=json.dumps(context.analyst_report, indent=2, ensure_ascii=False),
                plan=json.dumps(context.plan, indent=2, ensure_ascii=False),
                critic_issues=critic_issues,
            )

            response = llm.invoke([
                SystemMessage(content="You are a music arranger. Output ONLY JSON."),
                HumanMessage(content=prompt),
            ])

            cmd = extract_json(getattr(response, 'content', ''))
            if not cmd or cmd.get('done', False):
                break

            action_key = cmd.get('action', '')
            if action_key in used_actions:
                break
            used_actions.add(action_key)

            print(f"  [Arranger iter {iteration}] Executing: {json.dumps(cmd)}")
            piece = _execute_arrange(piece, cmd, context)
            set_piece_context(piece)
            report["actions"].append(cmd)

        report["tracks_after"] = len(piece.tracks)
        context.arrangement_report = report
        print(f"\n[Arranger] Done: {report}")
        return piece, report


def _execute_arrange(piece: mp.P, cmd: dict, context: RoleContext) -> mp.P:
    """Execute an arrangement action."""
    action = cmd.get('action', '')

    if action == 'arrange_for_piano':
        from tools.arrangement.arrange_piano import ArrangePianoTool
        from tools.analysis.extract_melody import ExtractMelodyTool
        from tools.analysis.analyze_harmony import AnalyzeHarmonyTool

        melody = ExtractMelodyTool().run(piece)
        harmony = AnalyzeHarmonyTool().run(piece, granularity='measure')
        style = cmd.get('style', 'classical')
        return ArrangePianoTool().run(piece, melody=melody, harmony=harmony, style=style)

    elif action == 'arrange_for_strings':
        from tools.arrangement.arrange_strings import ArrangeStringsTool
        voicing = cmd.get('voicing', 'standard')
        return ArrangeStringsTool().run(piece, voicing=voicing)

    elif action == 'arrange_for_winds':
        from tools.arrangement.arrange_winds import ArrangeWindsTool
        instrumentation = cmd.get('instrumentation', 'standard')
        return ArrangeWindsTool().run(piece, instrumentation=instrumentation)

    return piece
