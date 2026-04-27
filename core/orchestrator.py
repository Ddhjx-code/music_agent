"""
Role Orchestrator — multi-role collaboration pipeline.

Manages phase transitions between Planner, Analyst, Arranger,
Harmonist, Expression, and Critic roles. Handles Critic bounce-back
(max 2 retries per role).
"""

from __future__ import annotations

import json
import os

import musicpy as mp

from core.music_io import load_midi, save_midi
from core.roles.base import RoleContext
from core.roles.analyst_role import AnalystRole
from core.roles.planner_role import PlannerRole
from core.roles.arranger_role import ArrangerRole
from core.roles.harmonist_role import HarmonistRole
from core.roles.expression_role import ExpressionRole
from core.roles.critic_role import CriticRole
from agent.tool_registry import set_piece_context, get_piece_context

MAX_BOUNCES = 2


class RoleOrchestrator:
    """Orchestrate multi-role music processing pipeline."""

    def __init__(self, llm):
        self.llm = llm

    def run(self, piece: mp.P, instruction: str) -> mp.P:
        """Run the full pipeline."""
        context = RoleContext(instruction)

        # Phase 0: MIDI Fix (cleanup fragmentation, overlaps, out-of-range)
        print("\n=== Phase 0: MIDI Fix ===")
        piece = self._fix_midi(piece)

        # Phase 1: Pre-analysis (tools only, no LLM)
        print("\n=== Phase 1: Pre-Analysis ===")
        analyst = AnalystRole()
        piece, _ = analyst.run_tools_only(piece, context)

        # Phase 2: Planning
        print("\n=== Phase 2: Planning ===")
        planner = PlannerRole()
        piece, plan = planner.run(piece, context, self.llm)

        phases = plan.get("phases", [])
        params = plan.get("params", {})

        # Phase 3: Execute planned phases
        for phase in phases:
            if phase == "analysis":
                # Re-run full analysis with LLM summary
                print(f"\n=== Phase: Analysis ===")
                piece, _ = analyst.run(piece, context, self.llm)

            elif phase == "arrangement":
                print(f"\n=== Phase: Arrangement ===")
                arranger = ArrangerRole()
                piece, _ = self._with_bounce_back(piece, context, arranger, "arrangement")

            elif phase == "harmonist":
                print(f"\n=== Phase: Harmonist ===")
                harmonist = HarmonistRole()
                piece, report = harmonist.run(piece, context, self.llm)
                context.harmony_report = report

            elif phase == "expression":
                print(f"\n=== Phase: Expression ===")
                expression = ExpressionRole()
                piece, _ = self._with_bounce_back(piece, context, expression, "expression")

        # Phase 4: Critic review (with validation loop)
        print("\n=== Phase: Critic Review ===")
        critic = CriticRole()
        piece, critic_report = critic.run(piece, context, self.llm)

        bounce_count = 0
        while (not critic_report.get("passed", True)
               and bounce_count < MAX_BOUNCES):
            high_issues = [i for i in critic_report.get("issues", [])
                           if i.get("severity") == "high"]
            if not high_issues:
                break
            bounce_count += 1
            print(f"\n[Critic] Bounce-back #{bounce_count}")
            roles_with_issues = set(i.get("role", "") for i in high_issues)
            for role_name in roles_with_issues:
                context.critic_issues = [i for i in high_issues
                                         if i.get("role") == role_name]
                piece = self._bounce_back(piece, context, role_name)
            # Re-run Critic to verify fixes
            piece, critic_report = critic.run(piece, context, self.llm)

        return piece

    def _fix_midi(self, piece: mp.P) -> mp.P:
        """Run MIDI fix pipeline on a piece to clean up transcription artifacts."""
        import tempfile
        from core.midi_fixer import fix_midi, _rule_based_fallback

        # Save piece to temp MIDI
        tmp = tempfile.NamedTemporaryFile(suffix=".mid", delete=False)
        tmp_path = tmp.name
        tmp.close()

        from core.music_io import save_midi, load_midi
        save_midi(piece, tmp_path)

        try:
            fixed_path = fix_midi(tmp_path, stem_type="vocals")
            if fixed_path and os.path.exists(fixed_path):
                result = load_midi(fixed_path)
                if result and result.tracks:
                    print(f"  MIDI fix: {len(piece.tracks)} track(s), "
                          f"notes before={sum(len(t) for t in piece.tracks)}, "
                          f"after={sum(len(t) for t in result.tracks)}")
                    return result
        except Exception as e:
            print(f"  MIDI fix error: {e}, using original piece")

        return piece

    def _with_bounce_back(self, piece: mp.P, context: RoleContext,
                          role, role_key: str) -> tuple[mp.P, dict]:
        """Run a role with bounce-back support."""
        bounce_count = 0
        while bounce_count <= MAX_BOUNCES:
            piece, report = role.run(piece, context, self.llm)
            if bounce_count >= MAX_BOUNCES:
                break
            # Check if critic wants bounce back (from previous Critic run)
            if not context.critic_issues:
                break
            role_issues = [i for i in context.critic_issues if i.get("role") == role_key]
            if not role_issues:
                break
            bounce_count += 1
        return piece, report

    def _bounce_back(self, piece: mp.P, context: RoleContext, role_name: str) -> mp.P:
        """Bounce back to a specific role for rework."""
        if role_name == "arranger":
            arranger = ArrangerRole()
            piece, _ = arranger.run(piece, context, self.llm)
        elif role_name == "harmonist":
            harmonist = HarmonistRole()
            piece, _ = harmonist.run(piece, context, self.llm)
        elif role_name == "expression":
            expression = ExpressionRole()
            piece, _ = expression.run(piece, context, self.llm)
        return piece


# ── Backward compatibility ──────────────────────────────────────────


def create_music_agent(llm):
    """Deprecated: use RoleOrchestrator instead."""
    import warnings
    warnings.warn("create_music_agent is deprecated. Use RoleOrchestrator.", DeprecationWarning)

    orchestrator = RoleOrchestrator(llm)

    def agent_fn(piece, instruction: str):
        result_piece = orchestrator.run(piece, instruction)
        set_piece_context(result_piece)
        return []

    return agent_fn


def run_pipeline(midi_path: str, instruction: str, llm,
                 output_path: str = None) -> str:
    """Run the full Music Agent pipeline with multi-role orchestration."""
    piece = load_midi(midi_path)
    set_piece_context(piece)

    orchestrator = RoleOrchestrator(llm)
    result_piece = orchestrator.run(piece, instruction)

    if output_path is None:
        base, ext = os.path.splitext(midi_path)
        output_path = f"{base}_arranged{ext}"

    save_midi(result_piece, output_path)
    return output_path
