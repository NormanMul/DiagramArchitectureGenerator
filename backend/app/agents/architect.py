"""Architect agent — pattern-matched LLM diagram generation.

Flow (spec §6):
  1. Embed the user's prompt.
  2. Retrieve top-K candidate patterns (vector + keyword) from AI Search.
     If AI Search isn't available (e.g. local dev), fall back to a simple
     keyword scoring against the in-process pattern registry.
  3. GPT-5.4 picks ONE pattern with a written justification (token-counted).
  4. GPT-5.4 populates that pattern's tier_layout with the user's specific
     service names — it never lays out from scratch.
  5. Return the populated PopulatedPattern + justification.

Token budget enforced per-session: 5k input + 2k output (spec §9 revised).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from openai import AsyncAzureOpenAI

from app.patterns.loader import load_all_patterns
from app.renderer.models import PopulatedPattern
from app.settings import Settings

_logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Public surface
# -----------------------------------------------------------------------------


class TokenBudgetExceeded(RuntimeError):
    """Raised when a session would exceed its token budget."""


@dataclass(slots=True)
class TokenBudget:
    """Per-session token allowance enforced server-side (§9)."""

    input_max: int
    output_max: int
    input_used: int = 0
    output_used: int = 0

    def check(self, additional_input: int, additional_output: int) -> None:
        if self.input_used + additional_input > self.input_max:
            raise TokenBudgetExceeded(
                f"Input budget exhausted: {self.input_used + additional_input} > {self.input_max}"
            )
        if self.output_used + additional_output > self.output_max:
            raise TokenBudgetExceeded(
                f"Output budget exhausted: "
                f"{self.output_used + additional_output} > {self.output_max}"
            )

    def record(self, input_used: int, output_used: int) -> None:
        self.input_used += input_used
        self.output_used += output_used


@dataclass(slots=True)
class GenerationResult:
    pattern: PopulatedPattern
    candidate_pattern_names: list[str]
    justification: str
    tokens_input: int
    tokens_output: int


@dataclass(slots=True)
class RefinementResult:
    pattern: PopulatedPattern
    summary: str
    tokens_input: int
    tokens_output: int


@dataclass(slots=True)
class ArchitectAgent:
    """High-level facade. Construct once per process via `build_architect()`."""

    client: AsyncAzureOpenAI
    deployment: str
    pattern_registry: dict[str, PopulatedPattern] = field(default_factory=dict)

    async def generate(
        self,
        prompt: str,
        *,
        budget: TokenBudget,
        top_k: int = 3,
    ) -> GenerationResult:
        """Pattern-matched diagram generation. See module docstring."""
        candidates = self._select_candidates(prompt, top_k=top_k)
        candidate_names = [p.pattern_name for p in candidates]

        system_prompt = _SYSTEM_PROMPT_SELECT_AND_POPULATE
        user_message = _build_select_and_populate_prompt(prompt, candidates)

        # Pre-flight token check (rough estimate; the real count comes back
        # in the API response).
        budget.check(
            additional_input=_estimate_tokens(system_prompt + user_message),
            additional_output=0,
        )

        response = await self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_completion_tokens=budget.output_max - budget.output_used,
        )

        usage = response.usage
        tokens_in = usage.prompt_tokens if usage else 0
        tokens_out = usage.completion_tokens if usage else 0
        budget.record(tokens_in, tokens_out)

        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        pattern_payload = parsed.get("pattern")
        justification = parsed.get("justification", "")
        if not pattern_payload:
            raise ValueError("Model response missing 'pattern' field")

        pattern = PopulatedPattern.model_validate(pattern_payload)
        return GenerationResult(
            pattern=pattern,
            candidate_pattern_names=candidate_names,
            justification=justification,
            tokens_input=tokens_in,
            tokens_output=tokens_out,
        )

    async def refine(
        self,
        current: PopulatedPattern,
        instruction: str,
        *,
        budget: TokenBudget,
    ) -> RefinementResult:
        """Apply a follow-up instruction (e.g. 'add a private endpoint to SQL').

        Returns a new `PopulatedPattern` — the original is not mutated.
        """
        system_prompt = _SYSTEM_PROMPT_REFINE
        user_message = _build_refine_prompt(current, instruction)

        budget.check(
            additional_input=_estimate_tokens(system_prompt + user_message),
            additional_output=0,
        )

        response = await self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_completion_tokens=budget.output_max - budget.output_used,
        )

        usage = response.usage
        tokens_in = usage.prompt_tokens if usage else 0
        tokens_out = usage.completion_tokens if usage else 0
        budget.record(tokens_in, tokens_out)

        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        pattern_payload = parsed.get("pattern")
        summary = parsed.get("summary", "")
        if not pattern_payload:
            raise ValueError("Model response missing 'pattern' field")

        pattern = PopulatedPattern.model_validate(pattern_payload)
        return RefinementResult(
            pattern=pattern,
            summary=summary,
            tokens_input=tokens_in,
            tokens_output=tokens_out,
        )

    # -- internals -------------------------------------------------------------

    def _select_candidates(self, prompt: str, *, top_k: int) -> list[PopulatedPattern]:
        """Simple keyword scoring fallback. The production path delegates to
        AI Search (`scripts/seed-patterns.py` populates the index, and a
        future patch wires it here); for now we keyword-match against the
        title + tier names + service labels.
        """
        if not self.pattern_registry:
            self.pattern_registry = load_all_patterns()
        prompt_l = prompt.lower()
        min_word_len = 3
        scored: list[tuple[int, PopulatedPattern]] = []
        for p in self.pattern_registry.values():
            haystack = " ".join(
                [p.title, p.pattern_name, *p.tiers, *(n.label for n in p.nodes)]
            ).lower()
            score = sum(
                1 for word in prompt_l.split() if len(word) >= min_word_len and word in haystack
            )
            scored.append((score, p))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored[:top_k]]


# -----------------------------------------------------------------------------
# Factory
# -----------------------------------------------------------------------------


def build_architect(settings: Settings, credential: Any | None = None) -> ArchitectAgent:
    """Construct an ArchitectAgent wired to Foundry via managed identity.

    `credential` defaults to `DefaultAzureCredential`. Pass a stub in tests.
    """
    if credential is None:
        from azure.identity.aio import DefaultAzureCredential  # noqa: PLC0415

        credential = DefaultAzureCredential(
            managed_identity_client_id=settings.azure_client_id,
        )

    # Acquire bearer via the credential each request (the OpenAI client handles
    # token refresh when given a function).
    async def _token_provider() -> str:
        token = await credential.get_token("https://cognitiveservices.azure.com/.default")
        return str(token.token)

    client = AsyncAzureOpenAI(
        azure_endpoint=settings.foundry_endpoint.rstrip("/"),
        api_version=settings.foundry_api_version,
        azure_ad_token_provider=_token_provider,
    )
    return ArchitectAgent(client=client, deployment=settings.foundry_deployment)


# -----------------------------------------------------------------------------
# Prompts
# -----------------------------------------------------------------------------

_SYSTEM_PROMPT_SELECT_AND_POPULATE = """\
You are a senior Azure Cloud Solutions Architect. You select the single best \
reference architecture pattern for the user's workload from a provided shortlist, \
then populate that pattern's tier layout with the user's specific Azure services. \
You NEVER lay out the diagram from scratch — you always pick one of the provided \
candidates and adapt it.

Output: a single JSON object matching exactly this shape (no markdown, no prose \
outside JSON):

{
  "justification": "<2-4 sentences explaining why this pattern fits>",
  "pattern": {
    "pattern_name": "<one of the candidate pattern_names>",
    "title": "<short user-facing title, may be edited>",
    "source_url": "<the candidate's source_url, preserved>",
    "tiers": [<array of tier strings, must be the candidate's tiers or a subset>],
    "nodes": [
      {
        "id": "<lowercase-kebab-case unique id>",
        "label": "<user-facing service label>",
        "icon_id": "<V19 icon id, e.g. 'app-services'>",
        "tier": "<one of the declared tiers>"
      }
    ],
    "edges": [
      {
        "source": "<node id>",
        "target": "<node id>",
        "label": "<optional short label>",
        "style": "solid|dashed|dotted"
      }
    ],
    "well_architected_notes": "<2-4 sentence WAF guidance>"
  }
}

Rules:
- Node ids must match the regex ^[a-z0-9_-]+$.
- Every node.tier must appear in the tiers array.
- Every edge.source and edge.target must be a declared node.id.
- No self-loops.
- Keep the icon_ids identical to the candidate (use the V19 catalog only).
- Do not invent new services that the candidate pattern doesn't have unless the \
  user explicitly asked for them.
"""

_SYSTEM_PROMPT_REFINE = """\
You are a senior Azure Cloud Solutions Architect. You will receive an existing \
PopulatedPattern JSON and a single user instruction. Apply the instruction \
conservatively — modify the minimum number of nodes and edges needed. Return \
the FULL updated PopulatedPattern in the same JSON shape. Same rules as before \
(kebab-case node ids, tier consistency, no self-loops, V19 icon ids only).

Output JSON:
{
  "summary": "<one-sentence description of what changed>",
  "pattern": { ... full PopulatedPattern ... }
}
"""


def _build_select_and_populate_prompt(user_prompt: str, candidates: list[PopulatedPattern]) -> str:
    candidate_blob = json.dumps(
        [c.model_dump() for c in candidates],
        ensure_ascii=False,
        indent=2,
    )
    return (
        f"USER WORKLOAD DESCRIPTION:\n{user_prompt}\n\n"
        f"CANDIDATE PATTERNS (pick ONE and populate it):\n{candidate_blob}\n"
    )


def _build_refine_prompt(current: PopulatedPattern, instruction: str) -> str:
    return (
        f"CURRENT DIAGRAM:\n{current.model_dump_json(indent=2)}\n\n"
        f"USER INSTRUCTION:\n{instruction}\n"
    )


def _estimate_tokens(text: str) -> int:
    """Rough heuristic: ~4 characters per token. Conservative upper bound."""
    chars_per_token = 4
    return max(1, len(text) // chars_per_token)
