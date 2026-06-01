"""Stub architect agent for local dev / smoke tests.

Returns the top keyword-matched pattern directly, without calling Foundry.
Useful when the real Azure dependencies aren't provisioned yet — see
`Settings.stub_mode` (env: `ARCHGEN_STUB_MODE=true`).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.architect import (
    GenerationResult,
    RefinementResult,
    TokenBudget,
)
from app.patterns.loader import load_all_patterns
from app.renderer.models import PopulatedPattern


@dataclass(slots=True)
class StubArchitectAgent:
    """Deterministic, no-network agent. Matches the public surface of
    `ArchitectAgent` so it's a drop-in for /api/generate + /api/refine.
    """

    pattern_registry: dict[str, PopulatedPattern] = field(default_factory=dict)

    async def generate(
        self,
        prompt: str,
        *,
        budget: TokenBudget,
        top_k: int = 3,
    ) -> GenerationResult:
        if not self.pattern_registry:
            self.pattern_registry = load_all_patterns()
        candidates = _score(prompt, self.pattern_registry, top_k=top_k)
        choice = candidates[0]
        fake_in = min(500, budget.input_max - budget.input_used)
        fake_out = min(150, budget.output_max - budget.output_used)
        budget.record(fake_in, fake_out)
        return GenerationResult(
            pattern=choice,
            candidate_pattern_names=[c.pattern_name for c in candidates],
            justification=(
                f"[stub mode] Picked '{choice.pattern_name}' by keyword match. "
                f"In production GPT-5.4 would justify and adapt the pattern."
            ),
            tokens_input=fake_in,
            tokens_output=fake_out,
        )

    async def refine(
        self,
        current: PopulatedPattern,
        instruction: str,
        *,
        budget: TokenBudget,
    ) -> RefinementResult:
        # Stub: no-op refinement — return the input pattern unchanged with a
        # synthetic summary.
        fake_in = min(300, budget.input_max - budget.input_used)
        fake_out = min(80, budget.output_max - budget.output_used)
        budget.record(fake_in, fake_out)
        return RefinementResult(
            pattern=current,
            summary=f"[stub mode] Would apply: {instruction}",
            tokens_input=fake_in,
            tokens_output=fake_out,
        )


def _score(
    prompt: str, registry: dict[str, PopulatedPattern], *, top_k: int
) -> list[PopulatedPattern]:
    prompt_l = prompt.lower()
    min_word_len = 3
    scored: list[tuple[int, PopulatedPattern]] = []
    for p in registry.values():
        haystack = " ".join(
            [p.title, p.pattern_name, *p.tiers, *(n.label for n in p.nodes)]
        ).lower()
        score = sum(
            1 for word in prompt_l.split() if len(word) >= min_word_len and word in haystack
        )
        scored.append((score, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:top_k]]
