"""Base player classes for the game engine."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

import anthropic


class Player(ABC):
    """Minimal interface — implement these two methods to play."""

    name: str

    @abstractmethod
    async def express(self, observation: dict) -> dict:
        """Return {expression, spoken_line, expression_reasoning}."""

    @abstractmethod
    async def guess(self, observation: dict) -> dict:
        """Return {my_guess, guess_reasoning, ragaman, ragaman_reasoning}."""


class LLMPlayer(Player):
    """Player backed by an LLM. Supply a system_prompt for personality."""

    def __init__(
        self,
        name: str,
        system_prompt: str,
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.8,
    ) -> None:
        self.name = name
        self.system_prompt = system_prompt
        self.model = model
        self.temperature = temperature
        self._client = anthropic.AsyncAnthropic()

    async def express(self, obs: dict) -> dict:
        prompt = self._build_express_prompt(obs)
        return await self._call(prompt)

    async def guess(self, obs: dict) -> dict:
        prompt = self._build_guess_prompt(obs)
        return await self._call(prompt)

    # -- prompt builders --

    def _build_express_prompt(self, obs: dict) -> str:
        history = self._format_history(obs.get("history", []))
        interp_hint = ""
        if obs.get("turn", 1) == 1:
            interp_hint = (
                f'\nFirst turn: start by interpreting "{obs["criterion"]}" '
                "in your own way (2-3 sentences). Keep this interpretation "
                "for all turns.\n"
            )

        return f"""\
You are playing Ragaman.
Theme: "{obs['theme']}" / Criterion: "{obs['criterion']}" (1=lowest, 13=highest)
Turn {obs['turn']}/{obs['max_turns']}
{interp_hint}
Opponent's card (visible to you): **{obs['opponent_card']}**
{history}
Pick an item from the theme that matches {obs['opponent_card']} on your scale.

Reply in JSON (Japanese):
```json
{{
  {'"interpretation": "your interpretation of the criterion (2-3 sentences)",' if obs.get('turn', 1) == 1 else ''}
  "expression": "item name",
  "expression_reasoning": "why this item at this position (1-2 sentences)",
  "spoken_line": "what you say aloud (2-3 sentences, NO numbers/rankings)"
}}
```
Rules:
- spoken_line must NOT reveal the number or relative position
- Use your personality, not generic common sense
- Be consistent with previous expressions"""

    def _build_guess_prompt(self, obs: dict) -> str:
        history = self._format_history(obs.get("history", []))
        exprs = obs.get("expressions", {})
        opp_name = [k for k in exprs if k != self.name]
        opp_expr = ""
        if opp_name:
            opp_data = exprs[opp_name[0]]
            opp_expr = opp_data.get("expression", "?")

        return f"""\
Ragaman — guess phase.
Theme: "{obs['theme']}" / Criterion: "{obs['criterion']}"
Turn {obs['turn']}/{obs['max_turns']}

Your card is HIDDEN. You do NOT know what number it is.

Opponent looked at YOUR card and chose this answer:
「{opp_expr}」
{history}
Where does 「{opp_expr}」 fall on the opponent's "{obs['criterion']}" scale?
Use past turns to calibrate: what items did the opponent pick for known numbers?

Rules:
- The opponent's answer DIRECTLY reflects YOUR card's value, filtered through their personality.
- Focus on the ANSWER ITSELF and past patterns — not commentary or tone.
- The two cards are independent random draws. No correlation.

Reply in JSON:
```json
{{
  "opponent_scale_reading": "where does this answer fall on opponent's scale, based on past patterns (1-2 sentences)",
  "my_guess": <number 1-13>,
  "guess_reasoning": "why — reference specific past answers if available (1-2 sentences)",
  "ragaman": true/false,
  "ragaman_reasoning": "only declare if you have genuine confidence (1 sentence)"
}}
```"""

    def _format_history(self, history: list[dict]) -> str:
        if not history:
            return ""
        lines = ["\nPrevious turns:"]
        for h in history:
            cards = h["cards"]
            exprs = h["expressions"]
            guesses = h["guesses"]
            for pid in cards:
                opp = [k for k in cards if k != pid][0]
                lines.append(
                    f"  Turn {h['turn']}: {pid} expressed "
                    f'"{exprs[pid].get("expression", "?")}" '
                    f"for {cards[opp]}, "
                    f"guessed own={guesses[pid].get('my_guess', '?')} "
                    f"(actual={cards[pid]})"
                )
        return "\n".join(lines)

    # -- LLM call --

    async def _call(self, prompt: str) -> dict[str, Any]:
        for attempt in range(2):
            resp = await self._client.messages.create(
                model=self.model,
                max_tokens=1000,
                system=self.system_prompt,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
            )
            text = resp.content[0].text
            result = self._parse_json(text)
            if "parse_error" not in result:
                # Enforce spoken_line length limit
                if "spoken_line" in result:
                    result["spoken_line"] = result["spoken_line"][:100]
                if "expression" in result:
                    result["expression"] = result["expression"][:50]
                return result
            if attempt == 0:
                continue
        # Fallback: return minimal valid action
        return {"expression": "...", "spoken_line": "...",
                "my_guess": 7, "ragaman": False,
                "parse_error": True, "raw_text": text}

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        try:
            if "```json" in text:
                s = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                s = text.split("```")[1].split("```")[0].strip()
            elif "{" in text:
                s = text[text.index("{") : text.rindex("}") + 1]
            else:
                s = text
            return json.loads(s)
        except (json.JSONDecodeError, ValueError, IndexError):
            return {"raw_text": text, "parse_error": True}
