"""Planner role — parse user instruction into execution plan."""

from __future__ import annotations

import json

import musicpy as mp

from core.roles.base import Role, RoleContext


class PlannerRole(Role):
    name = "planner"
    max_iterations = 1

    def run(self, piece: mp.P, context: RoleContext, llm) -> tuple[mp.P, dict]:
        """Parse instruction + analyst report into a plan. Does not modify piece."""
        from core.prompt_loader import load_prompt
        from core.roles.utils import extract_json
        from langchain_core.messages import SystemMessage, HumanMessage

        template = load_prompt("planner")
        prompt = template.format(
            instruction=context.instruction,
            analyst_report=json.dumps(context.analyst_report, indent=2, ensure_ascii=False)
            if context.analyst_report else "(no analysis yet)",
        )

        response = llm.invoke([
            SystemMessage(content="You are a music production planner. Output ONLY JSON."),
            HumanMessage(content=prompt),
        ])

        raw = getattr(response, 'content', '')
        plan = extract_json(raw, {"phases": ["analysis", "arrangement", "expression"], "params": {}})
        context.plan = plan

        print(f"\n[Planner] Plan: {json.dumps(plan, indent=2)}")
        return piece, plan
