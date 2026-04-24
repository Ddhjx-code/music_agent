
"""
Base class for music agent roles.

Each role has a name, prompt template, tool list, max iterations,
and a run(piece, context) -> dict method.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import musicpy as mp


class RoleContext:
    """Structured context passed between roles."""

    def __init__(self, instruction: str):
        self.instruction = instruction
        self.plan: dict | None = None
        self.analyst_report: dict | None = None
        self.arrangement_report: dict | None = None
        self.harmony_report: dict | None = None
        self.expression_report: dict | None = None
        self.critic_issues: list[dict] | None = None

    def to_prompt_context(self) -> dict:
        """Convert to dict for prompt templating."""
        return {
            "instruction": self.instruction,
            "plan": self.plan,
            "analyst_report": self.analyst_report,
            "arrangement_report": self.arrangement_report,
            "harmony_report": self.harmony_report,
            "expression_report": self.expression_report,
            "critic_issues": self.critic_issues,
        }


class Role(ABC):
    name: str
    max_iterations: int = 1

    @abstractmethod
    def run(self, piece: mp.P, context: RoleContext, llm) -> tuple[mp.P, dict]:
        """Execute role task. Returns (updated_piece, structured_report)."""
        ...
