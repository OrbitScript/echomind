"""
echomind/reporter.py
─────────────────────
Live terminal reporter for EchoMind debates.

Renders:
  • Live debate feed — each argument as it arrives, colorized by persona
  • Emotional state indicators that update in real-time
  • Conviction bars showing how strongly each persona holds their view
  • Synthesis display with consensus/fault-line breakdown
  • Final summary table
"""

from __future__ import annotations

import shutil
import textwrap
from datetime import datetime
from typing import Dict, List, Optional

from echomind.engine import (
    Argument, DebateState, DebatePhase, EmotionalState,
    Persona, get_persona_library,
)


# ─── ANSI helpers ─────────────────────────────────────────────────────────────

class C:
    RST  = "\033[0m";  BOLD = "\033[1m";  DIM  = "\033[2m";  ITALIC = "\033[3m"
    RED  = "\033[31m"; GRN  = "\033[32m"; YLW  = "\033[33m"; BLU  = "\033[34m"
    MGT  = "\033[35m"; CYN  = "\033[36m"; GRY  = "\033[90m"
    BRED = "\033[91m"; BGRN = "\033[92m"; BYLW = "\033[93m"; BBLU = "\033[94m"
    BMGT = "\033[95m"; BCYN = "\033[96m"; BWHT = "\033[97m"

def col(t, *c): return "".join(getattr(C, k) for k in c) + str(t) + C.RST
def tw():       return shutil.get_terminal_size((100, 24)).columns
def hr(ch="─", color="GRY"): print(col(ch * tw(), color))


# ─── State display helpers ─────────────────────────────────────────────────────

STATE_ICON = {
    EmotionalState.CONFIDENT:  "●",
    EmotionalState.CURIOUS:    "◎",
    EmotionalState.FRUSTRATED: "▲",
    EmotionalState.PERSUADED:  "◐",
    EmotionalState.ENTRENCHED: "■",
    EmotionalState.CONCEDING:  "◑",
    EmotionalState.ENERGIZED:  "★",
}

STATE_COLOR = {
    EmotionalState.CONFIDENT:  "BGRN",
    EmotionalState.CURIOUS:    "BCYN",
    EmotionalState.FRUSTRATED: "BRED",
    EmotionalState.PERSUADED:  "BMGT",
    EmotionalState.ENTRENCHED: "BYLW",
    EmotionalState.CONCEDING:  "BBLU",
    EmotionalState.ENERGIZED:  "BWHT",
}

def conviction_bar(conviction: float, width: int = 10) -> str:
    filled = int(conviction * width)
    empty  = width - filled
    return "█" * filled + "░" * empty


BANNER = """
  ███████╗ ██████╗██╗  ██╗ ██████╗ ███╗   ███╗██╗███╗   ██╗██████╗
  ██╔════╝██╔════╝██║  ██║██╔═══██╗████╗ ████║██║████╗  ██║██╔══██╗
  █████╗  ██║     ███████║██║   ██║██╔████╔██║██║██╔██╗ ██║██║  ██║
  ██╔══╝  ██║     ██╔══██║██║   ██║██║╚██╔╝██║██║██║╚██╗██║██║  ██║
  ███████╗╚██████╗██║  ██║╚██████╔╝██║ ╚═╝ ██║██║██║ ╚████║██████╔╝
  ╚══════╝ ╚═════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═════╝
"""


# ─── Terminal Reporter ─────────────────────────────────────────────────────────

class TerminalReporter:
    """
    Prints the debate live as arguments arrive.
    Designed to be used as the on_argument callback in DebateOrchestrator.
    """

    def __init__(self, verbose: bool = False, show_state: bool = True):
        self.verbose    = verbose
        self.show_state = show_state
        self._last_round: Optional[int] = None

    def print_banner(self):
        for line in BANNER.strip("\n").split("\n"):
            print(col(line, "BMGT"))
        print(col("  The AI that argues with itself", "DIM"))
        print()

    def print_debate_header(self, state: DebateState):
        hr("═", "BMGT")
        print(col(f"  Topic:   {state.topic}", "BWHT", "BOLD"))
        names = "  ·  ".join(
            f"{p.icon} {p.name}" for p in state.personas
        )
        print(col(f"  Debaters: {names}", "GRY"))
        hr("═", "BMGT")
        print()

    def on_argument(self, arg: Argument, persona: Persona, state: DebateState):
        """Called each time a persona completes an argument."""
        W = tw()

        # Round header when round changes
        if arg.round_num != self._last_round:
            self._last_round = arg.round_num
            print()
            if arg.phase == DebatePhase.OPENING:
                label = "OPENING STATEMENTS"
            elif arg.phase == DebatePhase.SYNTHESIS:
                label = "SYNTHESIS"
            else:
                label = f"ROUND {arg.round_num}"
            hr("─", "GRY")
            print(col(f"  ◈  {label}", "BOLD", "BWHT"))
            hr("─", "GRY")
            print()

        # Persona header
        state_icon  = STATE_ICON.get(arg.emotional_state, "●")
        state_col   = STATE_COLOR.get(arg.emotional_state, "GRY")
        conv_bar    = conviction_bar(arg.conviction)

        # Color from persona
        p_color = persona.color.replace("\033[", "").replace("m", "")
        # Map ANSI code to our C class attribute
        ansi_map = {
            "92": "BGRN", "95": "BMGT", "96": "BCYN",
            "91": "BRED", "93": "BYLW", "94": "BBLU",
            "97": "BWHT", "35": "MGT",
        }
        p_col_name = ansi_map.get(p_color, "BWHT")

        name_line = (
            f"  {persona.icon}  {col(persona.name, p_col_name, 'BOLD')}  "
            f"{col(state_icon + ' ' + arg.emotional_state.value, state_col)}  "
            f"{col(conv_bar, 'GRY')}  "
            f"{col(f'{arg.conviction:.0%} conviction', 'DIM')}"
        )
        print(name_line)

        # Who they're addressing
        if arg.targets:
            target_names = []
            for tid in arg.targets:
                tp = state.get_persona(tid)
                if tp:
                    target_names.append(tp.name)
            if target_names:
                print(col(f"  ↳ addressing: {', '.join(target_names)}", "DIM"))

        print()

        # Argument content — wrapped and indented
        content   = arg.content.strip()
        wrap_width = min(W - 8, 90)
        wrapped   = textwrap.wrap(content, width=wrap_width)
        for line in wrapped:
            print(f"  {col(line, p_col_name)}")

        print()

    def print_persona_status_table(self, state: DebateState):
        """Print a table of all personas and their current emotional states."""
        W = tw()
        hr("─", "GRY")
        print(col("  Persona States", "BOLD", "GRY"))
        hr("─", "GRY")
        print()
        for p in state.personas:
            state_icon = STATE_ICON.get(p.emotional_state, "●")
            state_col  = STATE_COLOR.get(p.emotional_state, "GRY")
            conv_bar   = conviction_bar(p.conviction)

            ansi_map = {
                "92": "BGRN", "95": "BMGT", "96": "BCYN",
                "91": "BRED", "93": "BYLW", "94": "BBLU",
                "97": "BWHT", "35": "MGT",
            }
            p_color  = p.color.replace("\033[","").replace("m","")
            p_col_nm = ansi_map.get(p_color, "BWHT")

            print(
                f"  {p.icon}  {col(p.name.ljust(22), p_col_nm, 'BOLD')}  "
                f"{col((state_icon + ' ' + p.emotional_state.value).ljust(16), state_col)}  "
                f"{col(conv_bar, 'GRY')}  "
                f"{col(f'{p.conviction:.0%}', 'DIM')}"
            )
        print()

    def print_synthesis(self, state: DebateState):
        """Print the final synthesis in a beautiful block."""
        if not state.synthesis:
            return

        W = tw()
        print()
        hr("═", "BMGT")
        print(col("  👑  SYNTHESIS", "BOLD", "BMGT"))
        print(col(f"  Topic: {state.topic}", "GRY"))
        hr("═", "BMGT")
        print()

        # Print synthesis text, wrapping nicely
        wrap_width = min(W - 6, 92)
        in_section = False
        section_colors = {
            "CONSENSUS":   "BGRN",
            "FAULT LINES": "BRED",
            "WHAT MOVED":  "BYLW",
            "VERDICT":     "BCYN",
        }

        for line in state.synthesis.splitlines():
            line = line.rstrip()
            if not line:
                print()
                continue

            # Detect section headers
            matched_section = None
            for section in section_colors:
                if line.upper().startswith(section):
                    matched_section = section
                    break

            if matched_section:
                print()
                print(col(f"  ◈  {line}", section_colors[matched_section], "BOLD"))
                in_section = True
            else:
                # Wrap content
                wrapped = textwrap.wrap(line, width=wrap_width)
                for wl in wrapped:
                    color = "BWHT" if in_section else "GRY"
                    print(f"  {col(wl, color)}")

        print()

    def print_final_summary(self, state: DebateState):
        """Print a compact summary of the whole debate."""
        W   = tw()
        dur = ""
        if state.ended_at and state.started_at:
            secs = (state.ended_at - state.started_at).total_seconds()
            dur  = f"{secs:.0f}s"

        hr("═", "BMGT")
        print(col("  ◈  DEBATE COMPLETE", "BOLD", "BMGT"))
        hr("═", "BMGT")
        print()

        # Stats
        total_args = len([a for a in state.arguments if a.phase == DebatePhase.DEBATE])
        print(col(f"  Topic:     {state.topic[:W-14]}", "BWHT"))
        print(col(f"  Debaters:  {len(state.personas)}", "GRY"))
        print(col(f"  Rounds:    {state.round_num}", "GRY"))
        print(col(f"  Arguments: {total_args}", "GRY"))
        if dur:
            print(col(f"  Duration:  {dur}", "GRY"))
        print()

        # Consensus points
        if state.consensus_points:
            print(col("  ✓  Consensus reached on:", "BGRN", "BOLD"))
            for pt in state.consensus_points[:3]:
                wrapped = textwrap.wrap(pt, width=min(W-8, 88))
                for i, wl in enumerate(wrapped):
                    prefix = "     •  " if i == 0 else "        "
                    print(col(prefix + wl, "BGRN"))
            print()

        # Disagreement points
        if state.disagreement_points:
            print(col("  ✗  Persistent disagreements:", "BRED", "BOLD"))
            for pt in state.disagreement_points[:3]:
                wrapped = textwrap.wrap(pt, width=min(W-8, 88))
                for i, wl in enumerate(wrapped):
                    prefix = "     •  " if i == 0 else "        "
                    print(col(prefix + wl, "BRED"))
            print()

        # Final state of each persona
        self.print_persona_status_table(state)

        hr("═", "BMGT")
        print()


# ─── JSON / Markdown Reporters ────────────────────────────────────────────────

class JsonReporter:
    """Output the full debate as structured JSON."""

    def render(self, state: DebateState) -> str:
        import json
        return json.dumps(state.to_dict(), indent=2, default=str)

    def print(self, state: DebateState):
        print(self.render(state))

    def save(self, state: DebateState, path: str):
        with open(path, "w") as f:
            f.write(self.render(state))
        print(f"  Saved debate to: {path}")


class MarkdownReporter:
    """Output debate as Markdown — for GitHub, Notion, etc."""

    def render(self, state: DebateState) -> str:
        lines = []
        lines.append(f"# 🎭 EchoMind Debate")
        lines.append(f"\n**Topic:** {state.topic}")
        lines.append(f"\n**Debaters:** {', '.join(p.name for p in state.personas)}")
        lines.append(f"\n**Rounds:** {state.round_num}")
        lines.append(f"\n---\n")

        # Opening
        lines.append("## Opening Statements\n")
        for arg in state.arguments:
            if arg.phase != DebatePhase.OPENING:
                continue
            p = state.get_persona(arg.persona_id)
            if p:
                lines.append(f"### {p.icon} {p.name}")
                lines.append(f"\n{arg.content}\n")

        # Debate rounds
        current_round = None
        for arg in state.arguments:
            if arg.phase != DebatePhase.DEBATE:
                continue
            if arg.round_num != current_round:
                current_round = arg.round_num
                lines.append(f"\n## Round {current_round}\n")
            p = state.get_persona(arg.persona_id)
            if p:
                state_icon = STATE_ICON.get(arg.emotional_state, "●")
                lines.append(f"### {p.icon} {p.name} _{state_icon} {arg.emotional_state.value}_")
                lines.append(f"\n{arg.content}\n")

        # Synthesis
        if state.synthesis:
            lines.append("\n---\n")
            lines.append("## Synthesis\n")
            lines.append(state.synthesis)

        if state.consensus_points:
            lines.append("\n## Consensus Points\n")
            for pt in state.consensus_points:
                lines.append(f"- {pt}")

        if state.disagreement_points:
            lines.append("\n## Fault Lines\n")
            for pt in state.disagreement_points:
                lines.append(f"- {pt}")

        return "\n".join(lines)

    def print(self, state: DebateState):
        print(self.render(state))

    def save(self, state: DebateState, path: str):
        with open(path, "w") as f:
            f.write(self.render(state))
        print(f"  Saved markdown to: {path}")
