# 🎭 EchoMind — The AI That Argues With Itself

> *Give a topic. Watch multiple AI personas debate in real-time. Each has a worldview, an emotional state, and reacts to what the others actually say.*

EchoMind runs a live multi-party AI debate in your terminal. Not "5 perspectives on X" — a real debate where personas interrupt, reference each other's points, change their convictions, and sometimes fail to reach consensus.

---

## What It Looks Like

```
  ◈  OPENING STATEMENTS
  ─────────────────────────────────────────────────────────────────

  ⚙️  The Pragmatist  ● confident  ██████████  100% conviction

  Show me where this has worked before. Rewrites sound exciting
  in planning docs and fail in production. What's the evidence
  that the new system will be better? Who owns migration risk?

  ──────────────────────────────────────────────────────────────

  ✨  The Idealist  ● confident  ██████████  100% conviction

  The question isn't whether the rewrite is risky — it's whether
  the current system can carry us where we need to go. Technical
  debt compounds. The cost of not acting is invisible until it isn't.

  ◈  ROUND 1
  ─────────────────────────────────────────────────────────────────

  😈  Devil's Advocate  ▲ frustrated  ████████░░  82% conviction
  ↳ addressing: The Pragmatist, The Idealist

  You're both arguing past each other. Pragmatist wants evidence
  of success — but every system that got rewritten successfully
  was called "too risky" first. Idealist says technical debt
  compounds — but so does rewrite complexity. What's your actual
  stopping criterion?

  ⚙️  The Pragmatist  ◐ persuaded  ███████░░░  70% conviction
  ↳ addressing: Devil's Advocate

  Fair challenge. I'll grant the stopping criterion point —
  that's the real question. But I'd push back on the framing...
```

---

## Quick Start

```bash
git clone https://github.com/OrbitScript/echomind
cd echomind

# Configure your API key
python -m echomind --setup

# Run a debate
python -m echomind "Should we rewrite our codebase from scratch?"

# Pick your personas
python -m echomind "Is remote work better?" --personas pragmatist,idealist,devil,risk

# More rounds, save to file
python -m echomind "Should AI be regulated?" --rounds 4 --output debate.md

# See who's available
python -m echomind --list-personas

# Random demo topic
python -m echomind --demo
```

---

## The 8 Personas

| Persona | Archetype | Core Lens |
|---|---|---|
| ⚙️ **The Pragmatist** | Evidence-first | What works? Show me the data. |
| ✨ **The Idealist** | First-principles | What should be? Values drive reality. |
| 🔄 **The Systems Thinker** | Second-order | What are the downstream effects? |
| 😈 **The Devil's Advocate** | Contrarian | What's wrong with this? Stress-test everything. |
| ⚠️ **The Risk Analyst** | Downside-first | What's the worst case? Tail risks are underweighted. |
| 📜 **The Historian** | Pattern recognition | We've been here before. |
| 🔨 **The Builder** | Execution-first | Can we actually ship this? |
| ⚖️ **The Ethicist** | Consequence-focused | Who benefits and who bears the cost? |

---

## Emotional States

Personas don't just argue — their emotional state shifts based on what they hear:

| State | Trigger | Effect on Debate |
|---|---|---|
| ● Confident | Default | Clear, assertive arguments |
| ◎ Curious | New angle introduced | More questions, probing |
| ▲ Frustrated | Being misunderstood | Sharper, more direct |
| ◐ Persuaded | Compelling counter-argument | Acknowledges, adjusts |
| ■ Entrenched | Position challenged | Digs in, doubles down |
| ◑ Conceding | Valid point landed | Gives ground explicitly |
| ★ Energized | Late rounds, high conviction | Most direct, passionate |

Conviction level (shown as a bar) rises when entrenched, falls when persuaded.

---

## The Synthesis

After all debate rounds, a neutral synthesizer reads the transcript and produces:

- **CONSENSUS** — what all or most debaters actually agreed on
- **FAULT LINES** — where deep disagreement persisted and why  
- **WHAT MOVED** — which arguments visibly shifted positions
- **VERDICT** — what a thoughtful observer would honestly conclude

The synthesis doesn't manufacture agreement. If the debate deadlocked, it says so.

---

## CLI Reference

```bash
echomind "topic"                         # Run a debate
echomind "topic" --personas p1,p2,p3    # Pick personas
echomind "topic" --rounds 4              # More rounds (default: 3)
echomind "topic" --format json           # JSON output
echomind "topic" --format markdown       # Markdown output
echomind "topic" --output debate.json    # Save to file
echomind "topic" --no-state              # Hide emotional state bars
echomind --demo                          # Random built-in topic
echomind --list-personas                 # Show available personas
echomind --setup                         # Configure API key
```

---

## Providers

EchoMind works with any AI provider:

```bash
# Anthropic (Claude)
export ANTHROPIC_API_KEY=sk-ant-...

# OpenAI (GPT)
export OPENAI_API_KEY=sk-...

# Local (Ollama)
python -m echomind --setup   # choose option 3, enter http://localhost:11434/v1
```

---

## Python API

```python
from echomind.engine import DebateOrchestrator, get_persona_library
from echomind.reporter import TerminalReporter

library = get_persona_library()
personas = [library["pragmatist"], library["idealist"], library["devil"]]

reporter = TerminalReporter()
orchestrator = DebateOrchestrator(
    api_key="sk-ant-...",
    provider="anthropic",
    on_argument=reporter.on_argument,   # live terminal output
)

state = orchestrator.run(
    topic="Should we adopt microservices?",
    personas=personas,
    rounds=3,
)

reporter.print_synthesis(state)
reporter.print_final_summary(state)

# Access the full transcript
for arg in state.arguments:
    print(f"[{arg.persona_id}] {arg.content}")

# Save as JSON
import json
with open("debate.json", "w") as f:
    json.dump(state.to_dict(), f, indent=2, default=str)
```

---

## Architecture

```
User provides topic + persona selection
              ↓
    DebateOrchestrator.run()
              ↓
    Opening round: each persona states position
              ↓
    Debate rounds (1..N):
      For each persona:
        • Build context from full transcript
        • Detect who they're addressing
        • Call AI with persona's system prompt
        • EmotionEngine updates state + conviction
        • on_argument callback → live display
              ↓
    Synthesis round:
      • Neutral synthesizer reads full transcript
      • Produces Consensus / Fault Lines / What Moved / Verdict
      • Extract structured points
              ↓
    DebateState (complete transcript + synthesis + persona states)
```

---

## Zero Runtime Dependencies

Pure Python 3.8+. EchoMind calls AI APIs directly via `urllib` — no SDK needed.

```bash
python -m echomind --list-personas   # works immediately
```

---

## License

MIT
