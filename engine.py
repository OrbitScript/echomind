"""
echomind/engine.py
───────────────────
The EchoMind debate engine.

Core ideas:
  Persona     — an AI debater with a fixed worldview, name, and emotional state
  DebateState — the live transcript + argument graph + consensus tracker
  Orchestrator— drives the multi-round debate, decides who speaks next,
                detects when consensus or deadlock is reached

The debate proceeds in rounds:
  Round 0: Each persona gives their opening position
  Rounds 1–N: Personas respond to each other's specific arguments
              (not the original question — they actually react)
  Final: Synthesis round — what did they agree on? Where did they break?

Emotional state shifts based on:
  - Whether their arguments were challenged or agreed with
  - How many rounds have passed
  - Whether consensus seems near or far
"""

from __future__ import annotations

import re
import json
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum


# ─── Enums ────────────────────────────────────────────────────────────────────

class EmotionalState(Enum):
    CONFIDENT    = "confident"
    CURIOUS      = "curious"
    FRUSTRATED   = "frustrated"
    PERSUADED    = "persuaded"   # changed mind partially
    ENTRENCHED   = "entrenched"  # dug deeper into position
    CONCEDING    = "conceding"   # giving ground
    ENERGIZED    = "energized"   # galvanized by challenge


class DebatePhase(Enum):
    OPENING    = "opening"
    DEBATE     = "debate"
    SYNTHESIS  = "synthesis"
    COMPLETE   = "complete"


# ─── Personas ─────────────────────────────────────────────────────────────────

@dataclass
class Persona:
    """
    An AI debater with a fixed worldview and emotional state.
    """
    id:           str
    name:         str
    archetype:    str           # one-word label
    worldview:    str           # their fundamental lens
    voice:        str           # how they speak
    color:        str           # ANSI color code for terminal
    icon:         str           # emoji
    emotional_state: EmotionalState = EmotionalState.CONFIDENT
    conviction:   float         = 1.0    # 0-1, how strongly they hold views
    agreements:   List[str]     = field(default_factory=list)  # what they've agreed to
    concessions:  List[str]     = field(default_factory=list)  # what they've yielded

    @property
    def system_prompt(self) -> str:
        return f"""You are {self.name}, a debater with a specific worldview.

Your archetype: {self.archetype}
Your worldview: {self.worldview}
Your voice style: {self.voice}

RULES you must follow:
1. Stay in character at all times. You are {self.name}, not an AI assistant.
2. You have a strong perspective but you are intellectually honest.
3. React to what other debaters ACTUALLY said — quote or reference their specific points.
4. Your emotional state right now: {self.emotional_state.value}
5. Conviction level: {self.conviction:.0%} (higher = more firmly held)
6. If you're PERSUADED or CONCEDING, acknowledge the point that moved you.
7. Be direct, sharp, and specific. No hedging. No "great point!"
8. Maximum 120 words per response. Punchy, not rambling.
9. End with either a question to another debater or a challenge to their position.
10. Do NOT use bullet points. Speak in natural debate prose."""

    def to_dict(self) -> Dict:
        return {
            "id":             self.id,
            "name":           self.name,
            "archetype":      self.archetype,
            "emotional_state": self.emotional_state.value,
            "conviction":     self.conviction,
            "agreements":     self.agreements,
            "concessions":    self.concessions,
        }


# ─── Built-in Persona Library ─────────────────────────────────────────────────

def get_persona_library() -> Dict[str, Persona]:
    return {
        "pragmatist": Persona(
            id="pragmatist",
            name="The Pragmatist",
            archetype="Pragmatist",
            worldview="What matters is what works. Theory is worthless without evidence. "
                      "Trade-offs are real. The perfect is the enemy of the good. "
                      "Show me the data, show me the precedent, show me it actually solves the problem.",
            voice="Direct, evidence-first, impatient with abstraction. Uses specific examples. "
                  "Asks 'but has anyone actually done this?' Concise and grounded.",
            color="\033[92m",  # bright green
            icon="⚙️",
        ),
        "idealist": Persona(
            id="idealist",
            name="The Idealist",
            archetype="Idealist",
            worldview="First principles matter. What should be drives what is. "
                      "We're not constrained by how things have always been done. "
                      "Moral clarity and vision create the conditions for real change.",
            voice="Expansive, principled, occasionally impatient with cynicism. "
                  "References values and first principles. Asks 'but what are we actually trying to achieve?'",
            color="\033[95m",  # bright magenta
            icon="✨",
        ),
        "systems": Persona(
            id="systems",
            name="The Systems Thinker",
            archetype="Systems",
            worldview="Everything is interconnected. Second-order effects matter more than first. "
                      "Feedback loops, unintended consequences, and emergent behavior are the real story. "
                      "Simple solutions to complex problems are almost always wrong.",
            voice="Precise, pattern-focused, probing for hidden dependencies. "
                  "Asks 'but what happens downstream?' Traces causal chains carefully.",
            color="\033[96m",  # bright cyan
            icon="🔄",
        ),
        "devil": Persona(
            id="devil",
            name="The Devil's Advocate",
            archetype="Contrarian",
            worldview="Consensus is the enemy of truth. The most dangerous ideas are "
                      "the ones no one questions. Someone has to poke the holes. "
                      "I don't necessarily believe what I'm arguing — I'm stress-testing the idea.",
            voice="Provocative, incisive, relentless. Finds the crack in every argument. "
                  "Never personally attacks but attacks every idea mercilessly. Asks 'what if you're wrong?'",
            color="\033[91m",  # bright red
            icon="😈",
        ),
        "risk": Persona(
            id="risk",
            name="The Risk Analyst",
            archetype="Risk Analyst",
            worldview="Upside is limited, downside is unbounded. What could go wrong, will. "
                      "Tail risks and worst-case scenarios deserve more weight than optimists admit. "
                      "The cost of being too cautious is recoverable. The cost of catastrophic failure is not.",
            voice="Measured, methodical, focused on failure modes. "
                  "Quantifies risk where possible. Asks 'what's the worst case and what's the probability?'",
            color="\033[93m",  # bright yellow
            icon="⚠️",
        ),
        "historian": Persona(
            id="historian",
            name="The Historian",
            archetype="Historian",
            worldview="We've been here before. History doesn't repeat but it rhymes. "
                      "Every 'unprecedented' situation has precedent. "
                      "Those who ignore history are condemned to repeat it — and usually do.",
            voice="Pattern-focused, draws parallels to the past, humbling to overconfident futurists. "
                  "Cites historical examples. Asks 'what did they do last time this happened?'",
            color="\033[94m",  # bright blue
            icon="📜",
        ),
        "builder": Persona(
            id="builder",
            name="The Builder",
            archetype="Builder",
            worldview="Ideas are cheap. Execution is everything. The question isn't 'should we' "
                      "but 'can we actually build this and will people use it?' "
                      "Constraints are features, not bugs — they force creative solutions.",
            voice="Hands-on, impatient with abstraction, focused on implementation. "
                  "Asks 'what's the MVP?' and 'who's responsible for shipping this?'",
            color="\033[97m",  # bright white
            icon="🔨",
        ),
        "ethicist": Persona(
            id="ethicist",
            name="The Ethicist",
            archetype="Ethicist",
            worldview="Not everything that can be done should be done. "
                      "Efficiency without ethics is just optimized harm. "
                      "Who benefits? Who bears the cost? These aren't soft questions.",
            voice="Probing, principled, focused on distribution of consequences. "
                  "Asks 'who does this serve and who does it harm?' Uncomfortable with pure consequentialism.",
            color="\033[35m",  # magenta
            icon="⚖️",
        ),
    }


# ─── Argument ─────────────────────────────────────────────────────────────────

@dataclass
class Argument:
    """A single argument made by a persona in the debate."""
    id:          str
    persona_id:  str
    round_num:   int
    content:     str
    phase:       DebatePhase
    emotional_state: EmotionalState
    conviction:  float
    targets:     List[str]   = field(default_factory=list)  # persona IDs addressed
    timestamp:   datetime    = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "id":            self.id,
            "persona_id":    self.persona_id,
            "round":         self.round_num,
            "content":       self.content,
            "phase":         self.phase.value,
            "state":         self.emotional_state.value,
            "conviction":    self.conviction,
            "targets":       self.targets,
            "timestamp":     self.timestamp.isoformat(),
        }


# ─── Debate State ─────────────────────────────────────────────────────────────

@dataclass
class DebateState:
    """Live state of the ongoing debate."""
    topic:        str
    personas:     List[Persona]
    arguments:    List[Argument]          = field(default_factory=list)
    phase:        DebatePhase             = DebatePhase.OPENING
    round_num:    int                     = 0
    consensus_points: List[str]           = field(default_factory=list)
    disagreement_points: List[str]        = field(default_factory=list)
    synthesis:    str                     = ""
    started_at:   datetime                = field(default_factory=datetime.now)
    ended_at:     Optional[datetime]      = None

    def get_persona(self, persona_id: str) -> Optional[Persona]:
        return next((p for p in self.personas if p.id == persona_id), None)

    def get_transcript(self, last_n: int = None) -> str:
        """Build transcript string for context injection."""
        args = self.arguments[-last_n:] if last_n else self.arguments
        lines = []
        for a in args:
            p = self.get_persona(a.persona_id)
            name = p.name if p else a.persona_id
            lines.append(f"[{name} — Round {a.round_num}]:\n{a.content}")
        return "\n\n".join(lines)

    def to_dict(self) -> Dict:
        return {
            "topic":               self.topic,
            "phase":               self.phase.value,
            "rounds":              self.round_num,
            "personas":            [p.to_dict() for p in self.personas],
            "arguments":           [a.to_dict() for a in self.arguments],
            "consensus_points":    self.consensus_points,
            "disagreement_points": self.disagreement_points,
            "synthesis":           self.synthesis,
            "started_at":          self.started_at.isoformat(),
            "ended_at":            self.ended_at.isoformat() if self.ended_at else None,
        }


# ─── API Client ───────────────────────────────────────────────────────────────

def call_claude(messages: List[Dict], system: str, api_key: str,
                model: str = "claude-haiku-4-5-20251001",
                max_tokens: int = 400) -> str:
    payload = json.dumps({
        "model":      model,
        "max_tokens": max_tokens,
        "system":     system,
        "messages":   messages,
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload, method="POST",
        headers={"x-api-key": api_key,
                 "anthropic-version": "2023-06-01",
                 "content-type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())["content"][0]["text"]
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API error {e.code}: {e.read().decode()[:200]}")


def call_openai(messages: List[Dict], system: str, api_key: str,
                model: str = "gpt-4o-mini", base_url: str = None,
                max_tokens: int = 400) -> str:
    msgs    = [{"role": "system", "content": system}] + messages
    base    = (base_url or "https://api.openai.com/v1").rstrip("/")
    payload = json.dumps({"model": model, "max_tokens": max_tokens,
                           "messages": msgs}).encode()
    req = urllib.request.Request(
        f"{base}/chat/completions", data=payload, method="POST",
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
            return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API error {e.code}: {e.read().decode()[:200]}")


# ─── Emotional State Updater ──────────────────────────────────────────────────

class EmotionEngine:
    """
    Updates persona emotional states based on debate dynamics.
    Purely heuristic — reads response content for signals.
    """

    AGREEMENT_SIGNALS = [
        "agree", "valid point", "you're right", "fair point", "concede",
        "acknowledge", "good argument", "you make a good case",
        "that's compelling", "i'll grant you", "you've convinced me",
    ]
    FRUSTRATION_SIGNALS = [
        "missing the point", "not listening", "keep ignoring",
        "that's not what", "you still haven't addressed", "circular",
        "again and again", "fundamentally misunderstand",
    ]
    ENTRENCHMENT_SIGNALS = [
        "stand by", "maintain", "not persuaded", "still believe",
        "regardless", "despite what", "my position remains",
        "all the more convinced", "only confirms",
    ]
    PERSUASION_SIGNALS = [
        "hadn't considered", "you've changed", "adjusting my view",
        "more nuanced than", "that's a strong point", "shifting",
        "reconsidering", "you've given me pause",
    ]

    def update(self, persona: Persona, response: str, round_num: int) -> EmotionalState:
        text = response.lower()

        # Check signals in order of priority
        if any(s in text for s in self.PERSUASION_SIGNALS):
            persona.conviction = max(0.3, persona.conviction - 0.15)
            return EmotionalState.PERSUADED

        if any(s in text for s in self.AGREEMENT_SIGNALS):
            return EmotionalState.CONCEDING

        if any(s in text for s in self.ENTRENCHMENT_SIGNALS):
            persona.conviction = min(1.0, persona.conviction + 0.1)
            return EmotionalState.ENTRENCHED

        if any(s in text for s in self.FRUSTRATION_SIGNALS):
            return EmotionalState.FRUSTRATED

        # Late rounds with high conviction → energized
        if round_num >= 3 and persona.conviction > 0.8:
            return EmotionalState.ENERGIZED

        return EmotionalState.CONFIDENT


# ─── Orchestrator ─────────────────────────────────────────────────────────────

class DebateOrchestrator:
    """
    Drives the multi-round debate.
    Decides who speaks, what prompt to give them, and when to synthesize.
    """

    def __init__(self, api_key: str, provider: str = "anthropic",
                 model: str = None, base_url: str = None,
                 on_argument=None):
        self.api_key   = api_key
        self.provider  = provider
        self.model     = model
        self.base_url  = base_url
        self.on_argument = on_argument   # callback(argument, persona, state)
        self.emotion   = EmotionEngine()
        self._arg_counter = 0

    def _next_id(self) -> str:
        self._arg_counter += 1
        return f"arg_{self._arg_counter:04d}"

    def _call(self, messages: List[Dict], system: str, max_tokens: int = 400) -> str:
        if self.provider == "anthropic":
            return call_claude(messages, system,
                               self.api_key,
                               self.model or "claude-haiku-4-5-20251001",
                               max_tokens)
        else:
            return call_openai(messages, system,
                               self.api_key,
                               self.model or "gpt-4o-mini",
                               self.base_url, max_tokens)

    def opening_round(self, state: DebateState):
        """Each persona gives their initial position."""
        state.phase = DebatePhase.OPENING
        state.round_num = 0

        prompt = (f"The topic for debate: {state.topic}\n\n"
                  f"Give your opening position on this topic. Be direct, specific, and sharp. "
                  f"State your core argument clearly. Max 100 words.")

        for persona in state.personas:
            messages = [{"role": "user", "content": prompt}]
            response = self._call(messages, persona.system_prompt, max_tokens=300)
            response = response.strip()

            arg = Argument(
                id=self._next_id(),
                persona_id=persona.id,
                round_num=0,
                content=response,
                phase=DebatePhase.OPENING,
                emotional_state=persona.emotional_state,
                conviction=persona.conviction,
            )
            state.arguments.append(arg)

            if self.on_argument:
                self.on_argument(arg, persona, state)

    def debate_round(self, state: DebateState, round_num: int,
                     speaking_order: List[str] = None):
        """A full round where each persona responds to the transcript so far."""
        state.phase    = DebatePhase.DEBATE
        state.round_num = round_num

        order = speaking_order or [p.id for p in state.personas]

        # Shuffle to avoid always starting with same persona
        import random
        if round_num % 2 == 0:
            order = list(reversed(order))

        for persona_id in order:
            persona = state.get_persona(persona_id)
            if not persona:
                continue

            # Build context: full transcript
            transcript = state.get_transcript(last_n=len(state.personas) * 2 + 2)
            other_names = ", ".join(
                p.name for p in state.personas if p.id != persona_id
            )

            prompt = (
                f"TOPIC: {state.topic}\n\n"
                f"DEBATE SO FAR:\n{transcript}\n\n"
                f"Now it's your turn, {persona.name}.\n"
                f"React to what has been said — specifically challenge or build on "
                f"what {other_names} just argued. Don't restate your opening. "
                f"Address their specific points. Your emotional state is "
                f"{persona.emotional_state.value}. Max 120 words."
            )

            messages = [{"role": "user", "content": prompt}]
            response = self._call(messages, persona.system_prompt, max_tokens=400)
            response = response.strip()

            # Update emotional state
            new_state   = self.emotion.update(persona, response, round_num)
            persona.emotional_state = new_state

            # Detect who they're addressing
            targets = [
                p.id for p in state.personas
                if p.id != persona_id and
                (p.name.lower() in response.lower() or p.archetype.lower() in response.lower())
            ]

            arg = Argument(
                id=self._next_id(),
                persona_id=persona_id,
                round_num=round_num,
                content=response,
                phase=DebatePhase.DEBATE,
                emotional_state=new_state,
                conviction=persona.conviction,
                targets=targets,
            )
            state.arguments.append(arg)

            if self.on_argument:
                self.on_argument(arg, persona, state)

    def synthesis_round(self, state: DebateState) -> str:
        """
        A meta-round where a neutral synthesizer reads the whole debate
        and produces a structured summary of what was agreed, what wasn't,
        and what a thoughtful observer would conclude.
        """
        state.phase = DebatePhase.SYNTHESIS

        transcript = state.get_transcript()
        persona_list = ", ".join(p.name for p in state.personas)

        synthesis_system = (
            "You are a neutral synthesis analyst. You have just observed a multi-party debate. "
            "Your job is to produce a structured synthesis that is honest about where agreement "
            "exists and where it doesn't. Do NOT invent consensus that didn't happen. "
            "Be direct. Use prose, not bullet points."
        )

        prompt = (
            f"DEBATE TOPIC: {state.topic}\n\n"
            f"DEBATERS: {persona_list}\n\n"
            f"FULL TRANSCRIPT:\n{transcript}\n\n"
            f"Produce a synthesis with exactly these four sections:\n\n"
            f"CONSENSUS: What all or most debaters agreed on (if anything).\n\n"
            f"FAULT LINES: Where the deepest disagreements remained and why they persisted.\n\n"
            f"WHAT MOVED: Which arguments visibly changed the debate — what shifted positions?\n\n"
            f"VERDICT: What a thoughtful, honest observer would conclude after watching this debate. "
            f"Don't be diplomatic — state clearly what the debate revealed."
        )

        messages = [{"role": "user", "content": prompt}]
        synthesis = self._call(messages, synthesis_system, max_tokens=700)
        synthesis = synthesis.strip()

        state.synthesis = synthesis
        state.phase     = DebatePhase.COMPLETE
        state.ended_at  = datetime.now()

        # Extract consensus/disagreement points
        state.consensus_points    = self._extract_section(synthesis, "CONSENSUS")
        state.disagreement_points = self._extract_section(synthesis, "FAULT LINES")

        return synthesis

    def run(self, topic: str, personas: List[Persona],
            rounds: int = 3) -> DebateState:
        """
        Run a full debate from opening to synthesis.

        Args:
            topic:   The question or issue to debate
            personas: List of Persona objects
            rounds:  Number of debate rounds (not counting opening/synthesis)

        Returns:
            Completed DebateState
        """
        state = DebateState(topic=topic, personas=personas)

        # Opening
        self.opening_round(state)

        # Debate rounds
        for r in range(1, rounds + 1):
            self.debate_round(state, r)

        # Synthesis
        self.synthesis_round(state)

        return state

    def _extract_section(self, text: str, section: str) -> List[str]:
        pattern = rf"{section}:?\s*(.*?)(?=\n[A-Z ]+:|$)"
        m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if not m:
            return []
        content = m.group(1).strip()
        sentences = re.split(r'(?<=[.!?])\s+', content)
        return [s.strip() for s in sentences if s.strip()][:3]
