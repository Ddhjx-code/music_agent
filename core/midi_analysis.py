"""
MIDI structural analysis module.

Produces purely descriptive diagnostics — no judgments, no fixes.
All outputs are objective metrics that can be consumed by an LLM
or other decision layer.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

import pretty_midi


@dataclass
class FragmentChain:
    """Consecutive same-pitch note events."""
    pitch: int
    count: int
    span_sec: float
    start_sec: float
    end_sec: float

    @property
    def rate(self) -> float:
        return self.count / self.span_sec if self.span_sec > 0 else 0


@dataclass
class MidiDiagnostic:
    """Structured, judgment-free MIDI diagnostics."""
    # Basic stats
    note_count: int = 0
    duration_sec: float = 0.0
    bpm: float = 0.0
    pitch_range: tuple[int, int] = (0, 0)

    # Overlap
    overlap_rate: float = 0.0
    max_concurrent: int = 0
    total_events: int = 0

    # Fragmentation
    fragment_chains: list[FragmentChain] = field(default_factory=list)
    chain_count_2plus: int = 0
    chain_count_3plus: int = 0
    longest_chain: int = 0

    # Density
    density_per_10s: dict[str, int] = field(default_factory=dict)

    # Pitch distribution
    pitch_counts: dict[int, int] = field(default_factory=dict)
    top_pitches: list[tuple[int, int]] = field(default_factory=list)

    # Duration distribution
    duration_stats: dict[str, float] = field(default_factory=dict)
    duration_bins: dict[str, int] = field(default_factory=dict)

    # Velocity distribution
    velocity_stats: dict[str, float] = field(default_factory=dict)
    velocity_bins: dict[str, int] = field(default_factory=dict)

    def to_report(self) -> str:
        """Human-readable diagnostic report."""
        lines = []
        lines.append(f"Notes: {self.note_count}, Duration: {self.duration_sec:.1f}s, BPM: {self.bpm}")
        lines.append(f"Pitch range: {self.pitch_range[0]} - {self.pitch_range[1]}")
        lines.append("")

        lines.append(f"Overlap: {self.overlap_rate:.0%} of note pairs overlap, max {self.max_concurrent} concurrent")
        lines.append("")

        lines.append(f"Fragmentation: {self.chain_count_2plus} same-pitch chains (2+), "
                     f"{self.chain_count_3plus} chains (3+), longest={self.longest_chain}")
        if self.fragment_chains:
            lines.append("  Worst chains (3+):")
            for ch in self.fragment_chains[:10]:
                lines.append(f"    pitch={ch.pitch}, {ch.count} fragments, "
                             f"{ch.start_sec:.1f}-{ch.end_sec:.1f}s ({ch.span_sec:.1f}s), "
                             f"rate={ch.rate:.1f}/s")
        lines.append("")

        lines.append("Density (notes/10s):")
        for k, v in self.density_per_10s.items():
            bar = "█" * (v // 3) if v > 0 else ""
            lines.append(f"  {k}: {v:4d} {bar}")
        lines.append("")

        lines.append("Pitch distribution (top 10):")
        for p, c in self.top_pitches[:10]:
            pct = c / self.note_count * 100
            lines.append(f"  MIDI {p:3d}: {c:4d} ({pct:.0f}%)")
        lines.append("")

        lines.append("Duration: " +
                     ", ".join(f"{k}={v:.3f}s" for k, v in self.duration_stats.items()))
        lines.append("Velocity: " +
                     ", ".join(f"{k}={v}" for k, v in self.velocity_stats.items()))

        return "\n".join(lines)


def analyze_midi(midi_path: str, overlap_sample_hz: float = 10.0) -> MidiDiagnostic:
    """
    Produce a structured diagnostic for a MIDI file.

    Purely descriptive — no judgments, no fixes, no thresholds.
    The output is meant to be consumed by an LLM or decision layer
    that applies context-specific rules (e.g. stem type).

    Args:
        midi_path: Path to the MIDI file.
        overlap_sample_hz: Sampling rate for overlap detection.

    Returns:
        MidiDiagnostic with all metrics populated.
    """
    pm = pretty_midi.PrettyMIDI(midi_path)
    if not pm.instruments:
        return MidiDiagnostic()

    instr = pm.instruments[0]
    notes = sorted(instr.notes, key=lambda n: n.start)
    if not notes:
        return MidiDiagnostic()

    d = MidiDiagnostic()
    d.note_count = len(notes)
    d.duration_sec = max(n.end for n in notes) - min(n.start for n in notes)
    tempo_changes = pm.get_tempo_changes()
    d.bpm = float(tempo_changes[1][-1]) if len(tempo_changes[1]) > 0 else 120.0

    pitches = [n.pitch for n in notes]
    d.pitch_range = (min(pitches), max(pitches))

    # --- Overlap ---
    overlap_pairs = 0
    for i in range(1, len(notes)):
        if notes[i].start < notes[i - 1].end:
            overlap_pairs += 1
    d.total_events = len(notes) - 1
    d.overlap_rate = overlap_pairs / d.total_events if d.total_events > 0 else 0.0

    # Max concurrent via sampling
    step = 1.0 / overlap_sample_hz
    max_conc = 0
    t = notes[0].start
    end_t = max(n.end for n in notes)
    while t < end_t:
        active = sum(1 for n in notes if n.start <= t < n.end)
        if active > max_conc:
            max_conc = active
        t += step
    d.max_concurrent = max_conc

    # --- Fragmentation (consecutive same-pitch chains) ---
    chains: list[FragmentChain] = []
    start_idx = 0
    for i in range(1, len(notes)):
        if notes[i].pitch != notes[i - 1].pitch:
            if i - start_idx >= 2:
                chain_start = notes[start_idx].start
                chain_end = notes[i - 1].end
                chains.append(FragmentChain(
                    pitch=notes[start_idx].pitch,
                    count=i - start_idx,
                    span_sec=chain_end - chain_start,
                    start_sec=chain_start,
                    end_sec=chain_end,
                ))
            start_idx = i
    # last chain
    if len(notes) - start_idx >= 2:
        chain_start = notes[start_idx].start
        chain_end = notes[-1].end
        chains.append(FragmentChain(
            pitch=notes[start_idx].pitch,
            count=len(notes) - start_idx,
            span_sec=chain_end - chain_start,
            start_sec=chain_start,
            end_sec=chain_end,
        ))

    chains_sorted = sorted(chains, key=lambda c: c.rate, reverse=True)
    d.fragment_chains = chains_sorted
    d.chain_count_2plus = len(chains)
    d.chain_count_3plus = sum(1 for c in chains if c.count >= 3)
    d.longest_chain = max((c.count for c in chains), default=0)

    # --- Density ---
    for t_start in range(0, int(end_t) + 10, 10):
        t_end = t_start + 10
        count = sum(1 for n in notes if t_start <= n.start < t_end)
        if count > 0:
            d.density_per_10s[f"{t_start}-{t_end}s"] = count

    # --- Pitch distribution ---
    pc = Counter(pitches)
    d.pitch_counts = dict(pc)
    d.top_pitches = pc.most_common()

    # --- Duration ---
    durations = [n.end - n.start for n in notes]
    d.duration_stats = {
        "min": min(durations),
        "max": max(durations),
        "mean": sum(durations) / len(durations),
        "median": sorted(durations)[len(durations) // 2],
    }
    d.duration_bins = {
        "<0.15s": sum(1 for v in durations if v < 0.15),
        "0.15-0.3s": sum(1 for v in durations if 0.15 <= v < 0.3),
        "0.3-0.5s": sum(1 for v in durations if 0.3 <= v < 0.5),
        ">=0.5s": sum(1 for v in durations if v >= 0.5),
    }

    # --- Velocity ---
    velocities = [n.velocity for n in notes]
    d.velocity_stats = {
        "min": min(velocities),
        "max": max(velocities),
        "mean": round(sum(velocities) / len(velocities)),
    }
    d.velocity_bins = {
        "<40": sum(1 for v in velocities if v < 40),
        "40-69": sum(1 for v in velocities if 40 <= v < 70),
        "70-99": sum(1 for v in velocities if 70 <= v < 100),
        ">=100": sum(1 for v in velocities if v >= 100),
    }

    return d
