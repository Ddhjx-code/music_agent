"""Expression role — add velocity, timing, pedal."""

from __future__ import annotations

import json

import musicpy as mp

from core.roles.base import Role, RoleContext


class ExpressionRole(Role):
    name = "expression"
    max_iterations = 2

    def run(self, piece: mp.P, context: RoleContext, llm) -> tuple[mp.P, dict]:
        """Add musical expression. Max 2 iterations."""
        from core.prompt_loader import load_prompt
        from core.roles.utils import extract_json
        from langchain_core.messages import SystemMessage, HumanMessage
        from core.music_transform import piece_to_json
        from agent.tool_registry import set_piece_context

        template = load_prompt("expression")
        set_piece_context(piece)
        iteration = 0
        used_actions = set()
        report = {"actions": [], "velocity_changes": 0, "pedal_events": 0, "timing_applied": None}

        while iteration < self.max_iterations:
            iteration += 1
            music_json = piece_to_json(piece)
            critic_issues = json.dumps(context.critic_issues, indent=2) if context.critic_issues else "(none)"

            prompt = template.format(
                music_json=json.dumps(music_json, indent=2, ensure_ascii=False),
                arrangement_report=json.dumps(context.arrangement_report, indent=2, ensure_ascii=False) if context.arrangement_report else "(none)",
                harmony_report=json.dumps(context.harmony_report, indent=2, ensure_ascii=False) if context.harmony_report else "(none)",
                critic_issues=critic_issues,
            )

            response = llm.invoke([
                SystemMessage(content="You are an expression engineer. Output ONLY JSON."),
                HumanMessage(content=prompt),
            ])

            cmd = extract_json(getattr(response, 'content', ''))
            if not cmd or cmd.get('done', False):
                break

            action_key = cmd.get('action', '')
            if action_key in used_actions:
                break
            used_actions.add(action_key)

            print(f"  [Expression iter {iteration}] Executing: {json.dumps(cmd)}")
            piece = _execute_expression(piece, cmd, context)
            set_piece_context(piece)
            report["actions"].append(cmd)

        context.expression_report = report
        print(f"\n[Expression] Done: {report}")
        return piece, report


def _execute_expression(piece: mp.P, cmd: dict, context: RoleContext) -> mp.P:
    """Execute an expression action."""
    action = cmd.get('action', '')

    if action == 'adjust_velocity':
        from tools.expression.adjust_velocity import AdjustVelocityTool
        voice_roles = context.analyst_report.get('voice_roles', {}) if context.analyst_report else None
        return AdjustVelocityTool().run(
            piece,
            voice_roles=voice_roles,
            melody_boost=cmd.get('melody_boost', 10),
            accompaniment_reduce=cmd.get('accompaniment_reduce', 10),
        )

    elif action == 'apply_timing_variation':
        from tools.expression.timing_variation import ApplyTimingVariationTool
        return ApplyTimingVariationTool().run(
            piece,
            type=cmd.get('type', 'rubato'),
            amount=cmd.get('amount', 0.05),
        )

    elif action == 'add_sustain_pedal':
        from tools.expression.add_pedal import AddSustainPedalTool
        return AddSustainPedalTool().run(piece, mode=cmd.get('mode', 'harmonic_change'))

    return piece
