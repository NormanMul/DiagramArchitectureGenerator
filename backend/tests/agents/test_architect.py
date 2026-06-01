"""Architect agent tests — budget, candidate selection, generate/refine JSON parsing.
OpenAI client stubbed; no Foundry calls.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from app.agents.architect import (
    ArchitectAgent,
    TokenBudget,
    TokenBudgetExceeded,
    _build_refine_prompt,
    _build_select_and_populate_prompt,
    _estimate_tokens,
)
from app.patterns.loader import load_all_patterns
from app.renderer.models import Edge, Node, PopulatedPattern

# -----------------------------------------------------------------------------
# Fake OpenAI client
# -----------------------------------------------------------------------------


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeUsage:
    def __init__(self, prompt: int, completion: int) -> None:
        self.prompt_tokens = prompt
        self.completion_tokens = completion


class _FakeResponse:
    def __init__(self, content: str, prompt: int = 100, completion: int = 50) -> None:
        self.choices = [_FakeChoice(content)]
        self.usage = _FakeUsage(prompt, completion)


class _FakeCompletions:
    def __init__(self) -> None:
        self.response_content: str | None = None
        self.call_log: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> _FakeResponse:
        self.call_log.append(kwargs)
        assert self.response_content is not None
        return _FakeResponse(self.response_content)


class _FakeChat:
    def __init__(self) -> None:
        self.completions = _FakeCompletions()


class _FakeClient:
    def __init__(self) -> None:
        self.chat = _FakeChat()


@pytest.fixture
def fake_client() -> _FakeClient:
    return _FakeClient()


@pytest.fixture
def agent(fake_client: _FakeClient) -> ArchitectAgent:
    return ArchitectAgent(
        client=fake_client,  # type: ignore[arg-type]
        deployment="archgen-gpt54",
    )


def _make_pattern_with_edges() -> PopulatedPattern:
    return PopulatedPattern(
        pattern_name="basic-web-app",
        title="X",
        source_url="https://learn.microsoft.com/azure/architecture/x",
        tiers=["edge", "data"],
        nodes=[
            Node(id="a", label="A", icon_id="app-services", tier="edge"),
            Node(id="b", label="B", icon_id="azure-sql", tier="data"),
        ],
        edges=[Edge(source="a", target="b", label="ok")],
    )


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


class TestTokenBudget:
    def test_check_passes_within_budget(self) -> None:
        budget = TokenBudget(input_max=1000, output_max=500)
        budget.check(additional_input=500, additional_output=200)
        assert budget.input_used == 0

    def test_check_raises_when_input_exhausted(self) -> None:
        budget = TokenBudget(input_max=100, output_max=100)
        budget.record(80, 0)
        with pytest.raises(TokenBudgetExceeded, match="Input budget"):
            budget.check(additional_input=50, additional_output=0)

    def test_check_raises_when_output_exhausted(self) -> None:
        budget = TokenBudget(input_max=100, output_max=100)
        budget.record(0, 90)
        with pytest.raises(TokenBudgetExceeded, match="Output budget"):
            budget.check(additional_input=0, additional_output=20)

    def test_record_accumulates(self) -> None:
        budget = TokenBudget(input_max=100, output_max=100)
        budget.record(10, 5)
        budget.record(10, 5)
        assert budget.input_used == 20
        assert budget.output_used == 10


class TestEstimateTokens:
    def test_short_strings_have_minimum_of_one(self) -> None:
        assert _estimate_tokens("hi") == 1

    def test_grows_with_length(self) -> None:
        small = _estimate_tokens("a" * 40)
        big = _estimate_tokens("a" * 400)
        assert big > small


class TestPromptBuilders:
    def test_select_prompt_includes_candidates_and_user_prompt(self) -> None:
        load_all_patterns.cache_clear()
        candidates = list(load_all_patterns().values())[:2]
        prompt = _build_select_and_populate_prompt("my workload", candidates)
        assert "my workload" in prompt
        for c in candidates:
            assert c.pattern_name in prompt

    def test_refine_prompt_includes_current_and_instruction(self) -> None:
        current = _make_pattern_with_edges()
        prompt = _build_refine_prompt(current, "do this")
        assert "do this" in prompt
        assert current.pattern_name in prompt


class TestCandidateSelection:
    def test_returns_top_k(self, agent: ArchitectAgent) -> None:
        candidates = agent._select_candidates("hub spoke landing zone", top_k=3)
        assert len(candidates) == 3
        names = [c.pattern_name for c in candidates]
        assert "hub-spoke" in names

    def test_keyword_match_picks_aks_for_aks_prompt(self, agent: ArchitectAgent) -> None:
        candidates = agent._select_candidates("deploy aks baseline with workload identity", top_k=1)
        assert candidates[0].pattern_name == "aks-baseline"

    def test_no_keyword_match_still_returns_k(self, agent: ArchitectAgent) -> None:
        candidates = agent._select_candidates("xyzzy nothing matches", top_k=3)
        assert len(candidates) == 3


class TestGenerate:
    @pytest.mark.asyncio
    async def test_happy_path(self, agent: ArchitectAgent, fake_client: _FakeClient) -> None:
        pattern = _make_pattern_with_edges()
        fake_client.chat.completions.response_content = json.dumps(
            {"justification": "because reasons", "pattern": pattern.model_dump()}
        )
        budget = TokenBudget(input_max=10000, output_max=5000)
        result = await agent.generate("aks workload with cosmos", budget=budget)
        assert result.pattern.pattern_name == "basic-web-app"
        assert result.justification == "because reasons"
        assert result.tokens_input == 100
        assert result.tokens_output == 50
        assert budget.input_used == 100
        assert budget.output_used == 50

    @pytest.mark.asyncio
    async def test_invalid_json_raises(
        self, agent: ArchitectAgent, fake_client: _FakeClient
    ) -> None:
        fake_client.chat.completions.response_content = "{}"
        budget = TokenBudget(input_max=10000, output_max=5000)
        with pytest.raises(ValueError, match="missing 'pattern'"):
            await agent.generate("aks", budget=budget)

    @pytest.mark.asyncio
    async def test_pattern_validation_failure_propagates(
        self, agent: ArchitectAgent, fake_client: _FakeClient
    ) -> None:
        fake_client.chat.completions.response_content = json.dumps(
            {"justification": "x", "pattern": {"bogus": True}}
        )
        budget = TokenBudget(input_max=10000, output_max=5000)
        with pytest.raises(ValidationError):
            await agent.generate("aks", budget=budget)

    @pytest.mark.asyncio
    async def test_budget_exhausted_before_call(
        self, agent: ArchitectAgent, fake_client: _FakeClient
    ) -> None:
        budget = TokenBudget(input_max=10, output_max=5)
        with pytest.raises(TokenBudgetExceeded):
            await agent.generate("a very long prompt " * 50, budget=budget)
        assert fake_client.chat.completions.call_log == []


class TestRefine:
    @pytest.mark.asyncio
    async def test_happy_path(self, agent: ArchitectAgent, fake_client: _FakeClient) -> None:
        current = _make_pattern_with_edges()
        fake_client.chat.completions.response_content = json.dumps(
            {"summary": "added node", "pattern": current.model_dump()}
        )
        budget = TokenBudget(input_max=10000, output_max=5000)
        result = await agent.refine(current, "tweak it", budget=budget)
        assert result.summary == "added node"
        assert result.pattern.pattern_name == current.pattern_name

    @pytest.mark.asyncio
    async def test_refine_invalid_json_raises(
        self, agent: ArchitectAgent, fake_client: _FakeClient
    ) -> None:
        fake_client.chat.completions.response_content = "{}"
        budget = TokenBudget(input_max=10000, output_max=5000)
        with pytest.raises(ValueError, match="missing 'pattern'"):
            await agent.refine(_make_pattern_with_edges(), "x", budget=budget)
