#!/usr/bin/env python3
"""
echomind/cli.py — python -m echomind

Usage:
  python -m echomind "Should we rewrite our codebase from scratch?"
  python -m echomind "Is remote work better than office work?" --personas pragmatist,idealist,devil
  python -m echomind "Should AI be regulated?" --rounds 4 --format markdown
  python -m echomind --list-personas
  python -m echomind --demo
"""

import os
import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import echomind
from echomind.engine import DebateOrchestrator, DebateState, get_persona_library
from echomind.reporter import (
    TerminalReporter, JsonReporter, MarkdownReporter,
    BANNER, col, hr, C,
)


# ─── Config loader ─────────────────────────────────────────────────────────────

CONFIG_PATH = Path.home() / ".echomind" / "config.json"

def load_config() -> dict:
    cfg = {
        "api_key":  os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("OPENAI_API_KEY", ""),
        "provider": "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "openai",
        "model":    "",
        "base_url": "",
    }
    if CONFIG_PATH.exists():
        try:
            saved = json.loads(CONFIG_PATH.read_text())
            for k in ("api_key", "provider", "model", "base_url"):
                if saved.get(k):
                    cfg[k] = saved[k]
        except Exception:
            pass
    return cfg

def save_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


def setup_wizard():
    print(col("\n  🎭  EchoMind Setup\n", "BOLD", "BMGT"))
    print(col("  Choose your AI provider:", "GRY"))
    print("  1. Anthropic (Claude) — console.anthropic.com")
    print("  2. OpenAI             — platform.openai.com")
    print("  3. Other (Ollama, Groq, any OpenAI-compatible API)")
    print()
    choice = input(col("  Choice [1/2/3]: ", "BCYN")).strip()
    cfg = load_config()

    if choice == "1":
        cfg["provider"] = "anthropic"
        cfg["api_key"]  = input(col("  Anthropic API key: ", "BCYN")).strip()
        cfg["model"]    = input(col("  Model [claude-haiku-4-5-20251001]: ", "BCYN")).strip() or "claude-haiku-4-5-20251001"
        cfg["base_url"] = ""
    elif choice == "2":
        cfg["provider"] = "openai"
        cfg["api_key"]  = input(col("  OpenAI API key: ", "BCYN")).strip()
        cfg["model"]    = input(col("  Model [gpt-4o-mini]: ", "BCYN")).strip() or "gpt-4o-mini"
        cfg["base_url"] = ""
    else:
        cfg["provider"] = "openai"
        cfg["base_url"] = input(col("  Base URL (e.g. http://localhost:11434/v1): ", "BCYN")).strip()
        cfg["api_key"]  = input(col("  API key (or 'ollama'): ", "BCYN")).strip()
        cfg["model"]    = input(col("  Model name: ", "BCYN")).strip()

    save_config(cfg)
    print(col(f"\n  ✓  Saved to {CONFIG_PATH}\n", "BGRN"))
    return cfg


# ─── Persona listing ──────────────────────────────────────────────────────────

def print_persona_list():
    library = get_persona_library()
    print()
    hr("─", "GRY")
    print(col("  🎭  Available Personas", "BOLD", "BMGT"))
    hr("─", "GRY")
    print()
    for pid, p in library.items():
        ansi_map = {
            "92": "BGRN", "95": "BMGT", "96": "BCYN",
            "91": "BRED", "93": "BYLW", "94": "BBLU",
            "97": "BWHT", "35": "MGT",
        }
        p_color  = p.color.replace("\033[","").replace("m","")
        p_col_nm = ansi_map.get(p_color, "BWHT")

        print(f"  {p.icon}  {col(pid.ljust(16), p_col_nm, 'BOLD')}  {col(p.archetype.ljust(14), 'GRY')}  {p.worldview[:55]}…")
    print()
    print(col("  Use with: --personas pragmatist,idealist,devil,risk", "DIM"))
    print()


# ─── Demo mode ────────────────────────────────────────────────────────────────

DEMO_TOPICS = [
    "Should we rewrite our monolith as microservices?",
    "Is remote work better than office work long-term?",
    "Should AI development be paused until safety is solved?",
    "Should startups raise venture capital or stay bootstrapped?",
    "Is technical debt ever worth accumulating deliberately?",
]

DEFAULT_PERSONAS = ["pragmatist", "idealist", "devil", "risk"]


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        prog="echomind",
        description="EchoMind — The AI that argues with itself",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("topic",         nargs="?", default=None,
                   help="Topic or question for the debate")
    p.add_argument("--personas",    default=",".join(DEFAULT_PERSONAS),
                   help="Comma-separated list of persona IDs (default: pragmatist,idealist,devil,risk)")
    p.add_argument("--rounds",      type=int, default=3,
                   help="Number of debate rounds (default: 3)")
    p.add_argument("--format",      choices=["terminal", "json", "markdown"], default="terminal")
    p.add_argument("--output",      help="Save output to this file")
    p.add_argument("--provider",    choices=["anthropic", "openai", "other"], default=None)
    p.add_argument("--model",       default=None)
    p.add_argument("--api-key",     default=None)
    p.add_argument("--list-personas", action="store_true")
    p.add_argument("--setup",       action="store_true")
    p.add_argument("--demo",        action="store_true", help="Run with a built-in demo topic")
    p.add_argument("--no-state",    action="store_true", help="Hide emotional state indicators")
    p.add_argument("--version",     action="store_true")
    args = p.parse_args()

    if args.version:
        print(f"echomind {echomind.__version__}"); return

    if args.list_personas:
        print_persona_list(); return

    if args.setup:
        setup_wizard(); return

    # Print banner
    for line in BANNER.strip("\n").split("\n"):
        print(col(line, "BMGT"))
    print(col("  The AI that argues with itself\n", "DIM"))

    cfg = load_config()

    # CLI overrides
    if args.api_key:  cfg["api_key"]  = args.api_key
    if args.provider: cfg["provider"] = args.provider
    if args.model:    cfg["model"]    = args.model

    if not cfg.get("api_key"):
        print(col("  No API key found. Run: python -m echomind --setup\n", "BYLW"))
        return

    # Topic
    topic = args.topic
    if args.demo and not topic:
        import random
        topic = random.choice(DEMO_TOPICS)
        print(col(f"  Demo topic: {topic}\n", "GRY"))

    if not topic:
        print(col("  Provide a topic. Example:\n", "GRY"))
        print(col('  python -m echomind "Should we rewrite the codebase?"\n', "DIM"))
        print(col("  Or run with --demo for a random topic.\n", "GRY"))
        return

    # Persona selection
    library       = get_persona_library()
    persona_ids   = [pid.strip() for pid in args.personas.split(",") if pid.strip()]
    personas      = []
    unknown       = []
    for pid in persona_ids:
        if pid in library:
            personas.append(library[pid])
        else:
            unknown.append(pid)

    if unknown:
        print(col(f"  Unknown personas: {', '.join(unknown)}", "BYLW"))
        print(col(f"  Available: {', '.join(library.keys())}\n", "GRY"))

    if len(personas) < 2:
        print(col("  Need at least 2 personas to debate.", "BRED"))
        return

    # Non-terminal format — no live printing
    if args.format != "terminal":
        print(col(f"  Running debate: {topic}", "GRY"))
        print(col(f"  Personas: {', '.join(p.name for p in personas)}", "GRY"))
        print(col(f"  Rounds: {args.rounds}", "GRY"))
        print()

        orchestrator = DebateOrchestrator(
            api_key=cfg["api_key"],
            provider=cfg.get("provider", "anthropic"),
            model=cfg.get("model") or None,
            base_url=cfg.get("base_url") or None,
        )

        def quiet_callback(arg, persona, state):
            phase_label = arg.phase.value
            print(col(f"  ✓  {persona.name} [{phase_label} R{arg.round_num}]", "GRY"))

        orchestrator.on_argument = quiet_callback

        try:
            state = orchestrator.run(topic, personas, rounds=args.rounds)
        except Exception as e:
            print(col(f"\n  Error: {e}\n", "BRED"))
            return

        if args.format == "json":
            reporter = JsonReporter()
            if args.output:
                reporter.save(state, args.output)
            else:
                reporter.print(state)
        elif args.format == "markdown":
            reporter = MarkdownReporter()
            if args.output:
                reporter.save(state, args.output)
            else:
                reporter.print(state)
        return

    # ── Terminal mode — live debate ───────────────────────────────────────────
    reporter = TerminalReporter(show_state=not args.no_state)
    reporter.print_debate_header(
        # Create a minimal state for the header
        type("S", (), {"topic": topic, "personas": personas})()
    )

    orchestrator = DebateOrchestrator(
        api_key=cfg["api_key"],
        provider=cfg.get("provider", "anthropic"),
        model=cfg.get("model") or None,
        base_url=cfg.get("base_url") or None,
        on_argument=reporter.on_argument,
    )

    try:
        state = orchestrator.run(topic, personas, rounds=args.rounds)
    except KeyboardInterrupt:
        print(col("\n\n  Debate interrupted.\n", "BYLW"))
        return
    except Exception as e:
        print(col(f"\n  Error during debate: {e}\n", "BRED"))
        import traceback
        traceback.print_exc()
        return

    # Post-debate display
    reporter.print_synthesis(state)
    reporter.print_final_summary(state)

    # Optional save
    if args.output:
        if args.output.endswith(".json"):
            JsonReporter().save(state, args.output)
        elif args.output.endswith(".md"):
            MarkdownReporter().save(state, args.output)
        else:
            JsonReporter().save(state, args.output)


if __name__ == "__main__":
    main()
