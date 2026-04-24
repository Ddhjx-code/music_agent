"""Critic role — quality review and bounce-back."""

from __future__ import annotations

import json

import musicpy as mp

from core.roles.base import Role, RoleContext


class CriticRole(Role):
    name = "critic"
    max_iterations = 1

    def run(self, piece: mp.P, context: RoleContext, llm) -> tuple[mp.P, dict]:
        """Review piece and all reports. Returns {passed, issues}."""
        from core.prompt_loader import load_prompt
        from core.roles.utils import extract_json
        from langchain_core.messages import SystemMessage, HumanMessage
        from core.music_transform import piece_to_json

        template = load_prompt("critic")
        music_json = piece_to_json(piece)

        prompt = template.format(
            music_json=json.dumps(music_json, indent=2, ensure_ascii=False),
            analyst_report=json.dumps(context.analyst_report, indent=2, ensure_ascii=False) if context.analyst_report else "(none)",
            arrangement_report=json.dumps(context.arrangement_report, indent=2, ensure_ascii=False) if context.arrangement_report else "(none)",
            harmony_report=json.dumps(context.harmony_report, indent=2, ensure_ascii=False) if context.harmony_report else "(none)",
            expression_report=json.dumps(context.expression_report, indent=2, ensure_ascii=False) if context.expression_report else "(none)",
        )

        response = llm.invoke([
            SystemMessage(content="You are a quality reviewer. Output ONLY JSON."),
            HumanMessage(content=prompt),
        ])

        raw = getattr(response, 'content', '')
        report = extract_json(raw, {"passed": True, "issues": []})

        print(f"\n[Critic] Report: {json.dumps(report, indent=2, ensure_ascii=False)}")
        return piece, report
