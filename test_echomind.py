"""
tests/test_echomind.py
Full test suite for EchoMind — runs without an API key.
"""
import sys, json, re
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from echomind.engine import (
    Persona, Argument, DebateState, DebatePhase,
    EmotionalState, EmotionEngine, get_persona_library,
)
from echomind.reporter import (
    TerminalReporter, JsonReporter, MarkdownReporter,
    STATE_ICON, STATE_COLOR, conviction_bar,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_persona(pid="pragmatist") -> Persona:
    return get_persona_library()[pid]

def make_argument(persona_id="pragmatist", round_num=1,
                  content="Test argument.", phase=DebatePhase.DEBATE,
                  state=EmotionalState.CONFIDENT, conviction=0.8) -> Argument:
    return Argument(
        id=f"arg_{round_num}_{persona_id}",
        persona_id=persona_id,
        round_num=round_num,
        content=content,
        phase=phase,
        emotional_state=state,
        conviction=conviction,
    )

def make_state(topic="Test topic", persona_ids=None) -> DebateState:
    library = get_persona_library()
    ids = persona_ids or ["pragmatist", "idealist", "devil"]
    personas = [library[pid] for pid in ids]
    return DebateState(topic=topic, personas=personas)


# ─── Persona Library ──────────────────────────────────────────────────────────

class TestPersonaLibrary:
    def test_all_personas_have_required_fields(self):
        lib = get_persona_library()
        for pid, p in lib.items():
            assert p.id == pid
            assert p.name
            assert p.archetype
            assert p.worldview
            assert p.voice
            assert p.color
            assert p.icon
            assert p.system_prompt   # generated property

    def test_eight_personas_minimum(self):
        lib = get_persona_library()
        assert len(lib) >= 8

    def test_all_expected_personas_present(self):
        lib = get_persona_library()
        expected = ["pragmatist", "idealist", "systems", "devil",
                    "risk", "historian", "builder", "ethicist"]
        for pid in expected:
            assert pid in lib, f"Missing persona: {pid}"

    def test_system_prompt_contains_name(self):
        p = make_persona("pragmatist")
        assert "Pragmatist" in p.system_prompt

    def test_system_prompt_contains_worldview(self):
        p = make_persona("devil")
        assert "Contrarian" in p.system_prompt or "devil" in p.system_prompt.lower()

    def test_default_emotional_state(self):
        p = make_persona("idealist")
        assert p.emotional_state == EmotionalState.CONFIDENT

    def test_default_conviction(self):
        p = make_persona("risk")
        assert p.conviction == 1.0

    def test_to_dict(self):
        p = make_persona("historian")
        d = p.to_dict()
        assert "id"             in d
        assert "name"           in d
        assert "emotional_state" in d
        assert "conviction"     in d

    def test_personas_have_unique_colors(self):
        lib = get_persona_library()
        colors = [p.color for p in lib.values()]
        # Most should be distinct (some can share)
        assert len(set(colors)) >= 6

    def test_personas_have_unique_icons(self):
        lib = get_persona_library()
        icons = [p.icon for p in lib.values()]
        assert len(set(icons)) == len(icons), "All persona icons should be unique"


# ─── Argument ─────────────────────────────────────────────────────────────────

class TestArgument:
    def test_basic_creation(self):
        a = make_argument()
        assert a.persona_id == "pragmatist"
        assert a.round_num == 1

    def test_to_dict(self):
        a = make_argument()
        d = a.to_dict()
        assert "id"         in d
        assert "persona_id" in d
        assert "round"      in d
        assert "content"    in d
        assert "state"      in d
        assert "conviction" in d
        assert "timestamp"  in d

    def test_default_targets_empty(self):
        a = make_argument()
        assert a.targets == []

    def test_timestamp_set(self):
        a = make_argument()
        assert isinstance(a.timestamp, datetime)


# ─── Debate State ─────────────────────────────────────────────────────────────

class TestDebateState:
    def test_initial_phase(self):
        s = make_state()
        assert s.phase == DebatePhase.OPENING

    def test_get_persona(self):
        s = make_state()
        p = s.get_persona("pragmatist")
        assert p is not None
        assert p.name == "The Pragmatist"

    def test_get_persona_unknown(self):
        s = make_state()
        assert s.get_persona("nobody") is None

    def test_get_transcript_empty(self):
        s = make_state()
        assert s.get_transcript() == ""

    def test_get_transcript_with_args(self):
        s = make_state()
        s.arguments = [
            make_argument("pragmatist", 1, "Pragmatist says this."),
            make_argument("idealist",   1, "Idealist responds thus."),
        ]
        t = s.get_transcript()
        assert "Pragmatist says this." in t
        assert "Idealist responds thus." in t

    def test_get_transcript_last_n(self):
        s = make_state()
        s.arguments = [make_argument("pragmatist", i, f"Arg {i}") for i in range(10)]
        t = s.get_transcript(last_n=3)
        # Should only contain last 3
        assert "Arg 7" in t
        assert "Arg 9" in t
        assert "Arg 0" not in t

    def test_to_dict(self):
        s = make_state()
        d = s.to_dict()
        assert "topic"     in d
        assert "phase"     in d
        assert "personas"  in d
        assert "arguments" in d
        assert "synthesis" in d

    def test_personas_accessible(self):
        s = make_state(persona_ids=["pragmatist", "idealist"])
        assert len(s.personas) == 2

    def test_consensus_empty_by_default(self):
        s = make_state()
        assert s.consensus_points == []
        assert s.disagreement_points == []


# ─── Emotion Engine ───────────────────────────────────────────────────────────

class TestEmotionEngine:
    def _engine(self):
        return EmotionEngine()

    def test_persuasion_signals(self):
        e = self._engine()
        p = make_persona("pragmatist")
        state = e.update(p, "I hadn't considered that angle. You've given me pause.", 2)
        assert state == EmotionalState.PERSUADED

    def test_persuasion_reduces_conviction(self):
        e = self._engine()
        p = make_persona("pragmatist")
        original = p.conviction
        e.update(p, "You've changed how I see this. More nuanced than I thought.", 2)
        assert p.conviction < original

    def test_agreement_signal(self):
        e = self._engine()
        p = make_persona("idealist")
        state = e.update(p, "I agree that's a valid point and I'll concede it.", 2)
        assert state == EmotionalState.CONCEDING

    def test_entrenchment_signal(self):
        e = self._engine()
        p = make_persona("devil")
        state = e.update(p, "I still maintain my position regardless of what's been said.", 2)
        assert state == EmotionalState.ENTRENCHED

    def test_entrenchment_increases_conviction(self):
        e = self._engine()
        p = make_persona("devil")
        p.conviction = 0.7
        e.update(p, "I stand by every word I said. Not persuaded.", 2)
        assert p.conviction > 0.7

    def test_frustration_signal(self):
        e = self._engine()
        p = make_persona("systems")
        state = e.update(p, "You're missing the point entirely. Again and again.", 3)
        assert state == EmotionalState.FRUSTRATED

    def test_late_round_energized(self):
        e = self._engine()
        p = make_persona("risk")
        p.conviction = 0.9
        state = e.update(p, "The evidence is clear and I'm committed.", 5)
        assert state == EmotionalState.ENERGIZED

    def test_default_confident(self):
        e = self._engine()
        p = make_persona("builder")
        state = e.update(p, "Here's what we need to ship by end of sprint.", 1)
        assert state == EmotionalState.CONFIDENT

    def test_conviction_stays_bounded(self):
        e = self._engine()
        p = make_persona("pragmatist")
        p.conviction = 1.0
        e.update(p, "I stand by this and only confirms my view.", 2)
        assert p.conviction <= 1.0
        p.conviction = 0.05
        e.update(p, "You've completely changed my view. Reconsidering everything.", 2)
        assert p.conviction >= 0.0


# ─── Reporter (no API needed) ─────────────────────────────────────────────────

class TestReporter:
    def _complete_state(self) -> DebateState:
        s = make_state(topic="Should we rewrite our codebase?")
        s.arguments = [
            make_argument("pragmatist", 0, "Open position from pragmatist.",
                          phase=DebatePhase.OPENING),
            make_argument("idealist",   0, "Open position from idealist.",
                          phase=DebatePhase.OPENING),
            make_argument("devil",      0, "Open position from devil.",
                          phase=DebatePhase.OPENING),
            make_argument("pragmatist", 1, "Round 1 from pragmatist.",
                          phase=DebatePhase.DEBATE),
            make_argument("idealist",   1, "Round 1 from idealist.",
                          phase=DebatePhase.DEBATE),
            make_argument("devil",      1, "Round 1 from devil.",
                          phase=DebatePhase.DEBATE),
        ]
        s.synthesis = (
            "CONSENSUS: Both agreed technical debt is real.\n\n"
            "FAULT LINES: Deep disagreement on timeline and risk.\n\n"
            "WHAT MOVED: The pragmatist shifted slightly on timeline.\n\n"
            "VERDICT: The debate revealed a false dichotomy."
        )
        s.consensus_points    = ["Technical debt is real."]
        s.disagreement_points = ["Timeline for rewrite is disputed."]
        s.phase    = DebatePhase.COMPLETE
        s.round_num = 1
        s.ended_at = datetime.now()
        return s

    def test_conviction_bar(self):
        assert conviction_bar(1.0) == "██████████"
        assert conviction_bar(0.0) == "░░░░░░░░░░"
        assert conviction_bar(0.5) == "█████░░░░░"

    def test_state_icons_all_states_covered(self):
        for state in EmotionalState:
            assert state in STATE_ICON, f"Missing icon for {state}"
            assert state in STATE_COLOR, f"Missing color for {state}"

    def test_json_reporter(self):
        state = self._complete_state()
        r     = JsonReporter()
        out   = r.render(state)
        data  = json.loads(out)
        assert "topic"     in data
        assert "arguments" in data
        assert "synthesis" in data
        assert data["topic"] == "Should we rewrite our codebase?"

    def test_json_reporter_save(self, tmp_path=None):
        import tempfile, os
        state = self._complete_state()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            JsonReporter().save(state, path)
            with open(path) as f:
                data = json.load(f)
            assert "topic" in data
        finally:
            os.unlink(path)

    def test_markdown_reporter(self):
        state = self._complete_state()
        md    = MarkdownReporter().render(state)
        assert "# 🎭 EchoMind Debate" in md
        assert "Should we rewrite our codebase?" in md
        assert "Opening Statements" in md
        assert "Synthesis" in md

    def test_markdown_reporter_save(self, tmp_path=None):
        import tempfile, os
        state = self._complete_state()
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            path = f.name
        try:
            MarkdownReporter().save(state, path)
            content = Path(path).read_text()
            assert "EchoMind" in content
        finally:
            os.unlink(path)

    def test_terminal_reporter_on_argument(self, capsys=None):
        """TerminalReporter.on_argument should not raise."""
        import io
        from contextlib import redirect_stdout
        state    = self._complete_state()
        reporter = TerminalReporter()
        persona  = state.personas[0]
        arg      = state.arguments[0]
        buf      = io.StringIO()
        with redirect_stdout(buf):
            reporter.on_argument(arg, persona, state)
        output = buf.getvalue()
        assert len(output) > 0

    def test_terminal_persona_status_table(self):
        import io
        from contextlib import redirect_stdout
        state    = self._complete_state()
        reporter = TerminalReporter()
        buf      = io.StringIO()
        with redirect_stdout(buf):
            reporter.print_persona_status_table(state)
        output = buf.getvalue()
        assert "Pragmatist" in output or "pragmatist" in output.lower()


# ─── Orchestrator section extraction ─────────────────────────────────────────

class TestOrchestrator:
    def test_extract_section_consensus(self):
        from echomind.engine import DebateOrchestrator
        orch = DebateOrchestrator.__new__(DebateOrchestrator)
        text = ("CONSENSUS: Both sides agreed on X. They also agreed on Y.\n\n"
                "FAULT LINES: Disagreement on Z persisted throughout.\n\n"
                "VERDICT: Overall, unclear.")
        pts = orch._extract_section(text, "CONSENSUS")
        assert len(pts) >= 1
        assert any("agreed" in p for p in pts)

    def test_extract_section_missing(self):
        from echomind.engine import DebateOrchestrator
        orch = DebateOrchestrator.__new__(DebateOrchestrator)
        pts = orch._extract_section("No sections here", "CONSENSUS")
        assert pts == []

    def test_extract_section_fault_lines(self):
        from echomind.engine import DebateOrchestrator
        orch = DebateOrchestrator.__new__(DebateOrchestrator)
        text = "FAULT LINES: Deep disagreement on timeline and risk tolerance.\nVERDICT: Hard to say."
        pts = orch._extract_section(text, "FAULT LINES")
        assert len(pts) >= 1

    def test_debate_state_phases(self):
        """Verify DebatePhase enum has all expected values."""
        phases = [p.value for p in DebatePhase]
        assert "opening"   in phases
        assert "debate"    in phases
        assert "synthesis" in phases
        assert "complete"  in phases

    def test_emotional_state_enum(self):
        states = [s.value for s in EmotionalState]
        assert "confident"  in states
        assert "frustrated" in states
        assert "persuaded"  in states
        assert "entrenched" in states
        assert "energized"  in states


# ─── CLI unit tests (no API) ──────────────────────────────────────────────────

class TestCLI:
    def test_list_personas_no_crash(self):
        """list-personas should not raise."""
        import io
        from contextlib import redirect_stdout
        from echomind.cli import print_persona_list
        buf = io.StringIO()
        with redirect_stdout(buf):
            print_persona_list()
        assert "pragmatist" in buf.getvalue().lower()

    def test_demo_topics_exist(self):
        from echomind.cli import DEMO_TOPICS, DEFAULT_PERSONAS
        assert len(DEMO_TOPICS) >= 3
        assert len(DEFAULT_PERSONAS) >= 3

    def test_default_personas_in_library(self):
        from echomind.cli import DEFAULT_PERSONAS
        lib = get_persona_library()
        for pid in DEFAULT_PERSONAS:
            assert pid in lib, f"Default persona {pid} not in library"

    def test_config_load_returns_dict(self):
        from echomind.cli import load_config
        cfg = load_config()
        assert isinstance(cfg, dict)
        assert "provider" in cfg

    def test_banner_exists(self):
        from echomind.reporter import BANNER
        assert "ECHOMIND" in BANNER.upper() or "██" in BANNER


# ─── Runner ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import traceback
    passed = failed = 0
    classes = [
        TestPersonaLibrary, TestArgument, TestDebateState,
        TestEmotionEngine, TestReporter, TestOrchestrator, TestCLI,
    ]
    for cls in classes:
        inst = cls()
        for name in sorted(dir(cls)):
            if not name.startswith("test_"): continue
            try:
                getattr(inst, name)()
                print(f"  ✓ {cls.__name__}.{name}")
                passed += 1
            except Exception as e:
                print(f"  ✗ {cls.__name__}.{name}: {e}")
                if "--verbose" in sys.argv: traceback.print_exc()
                failed += 1
    print(f"\n  {passed} passed, {failed} failed")
    if failed: sys.exit(1)
