# Changelog

## [1.0.0] - 2026-04-20

### Added
- 8 built-in personas: Pragmatist, Idealist, Systems Thinker, Devil's Advocate,
  Risk Analyst, Historian, Builder, Ethicist
- 3-phase debate structure: Opening → Debate rounds → Synthesis
- Emotional state engine: 7 states (Confident, Curious, Frustrated, Persuaded,
  Entrenched, Conceding, Energized) with real-time shifts
- Conviction tracking per persona, updated by debate dynamics
- Target-addressing: personas detect and explicitly react to each other
- Live terminal display with colorized per-persona output
- Synthesis generator: Consensus / Fault Lines / What Moved / Verdict
- 3 output formats: terminal (live), JSON, Markdown
- Setup wizard for Anthropic, OpenAI, and any OpenAI-compatible API
- CLI: --personas, --rounds, --format, --output, --demo, --list-personas
- Zero runtime dependencies (pure Python stdlib + AI API)
- 50 tests, all passing without an API key
