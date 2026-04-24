"""Harmonist role — generate accompaniment."""

from __future__ import annotations

import json

import musicpy as mp

from core.roles.base import Role, RoleContext


class HarmonistRole(Role):
    name = "harmonist"
    max_iterations = 2

    def run(self, piece: mp.P, context: RoleContext, llm) -> tuple[mp.P, dict]:
        """Generate accompaniment. Max 2 iterations."""
        from core.prompt_loader import load_prompt
        from core.roles.utils import extract_json
        from langchain_core.messages import SystemMessage, HumanMessage
        from core.music_transform import piece_to_json
        from agent.tool_registry import set_piece_context
        from tools.harmony.generate_accompaniment import GenerateAccompanimentTool

        template = load_prompt("harmonist")
        set_piece_context(piece)
        report = {"actions": [], "notes_added": 0}

        harmony = context.analyst_report.get('harmony', []) if context.analyst_report else []
        if not harmony:
            print("[Harmonist] No harmony data available, skipping.")
            return piece, report

        music_json = piece_to_json(piece)
        plan = context.plan or {}
        harm_params = plan.get("params", {}).get("harmonist", {})

        prompt = template.format(
            music_json=json.dumps(music_json, indent=2, ensure_ascii=False),
            analyst_report=json.dumps(context.analyst_report, indent=2, ensure_ascii=False),
            plan=json.dumps(plan, indent=2, ensure_ascii=False),
            critic_issues=json.dumps(context.critic_issues, indent=2) if context.critic_issues else "(none)",
        )

        try:
            response = llm.invoke([
                SystemMessage(content="You are a harmonist. Output ONLY JSON."),
                HumanMessage(content=prompt),
            ])
            cmd = extract_json(getattr(response, 'content', ''))
            if cmd and not cmd.get('done', False):
                style = cmd.get('style', harm_params.get('style', 'classical'))
                pattern = cmd.get('pattern', harm_params.get('pattern', 'broken_chord'))
                accompaniment = GenerateAccompanimentTool().run(
                    harmony, style=style, pattern=pattern,
                )
                new_piece = mp.P(
                    tracks=[*piece.tracks, accompaniment],
                    instruments=[*piece.instruments, 1],
                    start_times=[*piece.start_times, 0],
                    bpm=piece.bpm if piece.bpm else 120,
                )
                report["notes_added"] = len(accompaniment) if hasattr(accompaniment, '__len__') else 0
                report["actions"].append(cmd)
                set_piece_context(new_piece)
                return new_piece, report
        except Exception as e:
            print(f"[Harmonist] LLM unavailable: {e}")

        # Fallback: generate with defaults
        style = harm_params.get('style', 'classical')
        pattern = harm_params.get('pattern', 'broken_chord')
        accompaniment = GenerateAccompanimentTool().run(
            harmony, style=style, pattern=pattern,
        )
        new_piece = mp.P(
            tracks=[*piece.tracks, accompaniment],
            instruments=[*piece.instruments, 1],
            start_times=[*piece.start_times, 0],
            bpm=piece.bpm if piece.bpm else 120,
        )
        report["notes_added"] = len(accompaniment) if hasattr(accompaniment, '__len__') else 0
        set_piece_context(new_piece)
        return new_piece, report
