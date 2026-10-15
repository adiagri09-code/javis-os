"""Fast mode helpers (0.164.0): support matrix, per-provider parameters, refusal detection,
the per-turn ContextVar and the last observed state per brain.

    python tests/run.py fast_mode
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import json
import sys

import fast_mode as F  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(extra) + "]") if extra and not cond else ""))
    if not cond:
        fails.append(name)


# Support matrix (spec: Claude only Opus 5.5, Opus 5, Opus 4.8; empty model or the "opus" alias is Opus 5.5).
for m, ok in (("", True), ("opus", True), ("claude-opus-5-5", True), ("claude-opus-5", True), ("claude-opus-4-8", True),
              ("claude-opus-4-7", False), ("claude-sonnet-5-5", False), ("sonnet", False), ("claude-opus-5-50", False),
              ("claude-opus-5-20261001", True), ("claude-opus-5-5-20261001", True)):
    check(f"claude_supports({m!r}) == {ok}", F.claude_supports(m) is ok)

check("Claude Code settings only when on and supported",
      json.loads(F.claude_sdk_settings("claude-opus-5-5", True) or "{}") == {"fastMode": True}
      and F.claude_sdk_settings("claude-opus-5-5", False) is None and F.claude_sdk_settings("claude-sonnet-5-5", True) is None)

h, b = F.anthropic_params("claude-opus-4-8", True)
check("Anthropic API: beta header and speed when on", h == {"anthropic-beta": "fast-mode-2026-02-01"} and b == {"speed": "fast"}, (h, b))
check("Anthropic API: nothing when off or unsupported",
      F.anthropic_params("claude-opus-4-8", False) == ({}, {}) and F.anthropic_params("claude-sonnet-5-5", True) == ({}, {}))

check("OpenAI API uses service_tier fast", F.compat_params("openai", True) == {"service_tier": "fast"})
check("OpenRouter and Gemini use service_tier priority",
      F.compat_params("openrouter", True) == {"service_tier": "priority"} and F.compat_params("gemini", True) == {"service_tier": "priority"})
check("brains without Fast mode get nothing",
      all(F.compat_params(p, True) == {} for p in ("groq", "deepseek", "ollama", "ollama-local", "grok-cli", "antigravity-cli")))
check("compat params are empty when off", F.compat_params("openai", False) == {})
check("ChatGPT OAuth Responses uses service_tier priority only when on",
      F.responses_params(True) == {"service_tier": "priority"} and F.responses_params(False) == {})

check("Codex on with a priority tier asks for priority", F.codex_override("gpt-6.1-sol", True, ["priority"]) == 'service_tier="priority"')
check("Codex off forces the normal tier (some models default to priority)", F.codex_override("gpt-6-sol", False, ["priority"]) == 'service_tier="default"')
check("Codex on for a model without a priority tier sends nothing", F.codex_override("x", True, []) is None)
check("Codex off for a model without tiers still forces default (config may set priority)", F.codex_override("x", False, []) == 'service_tier="default"')

check("refused: 400 naming the parameter", F.refused(400, "This model does not support the `speed` parameter", "speed"))
check("refused: 422 naming service_tier", F.refused(422, "invalid value for service_tier", "service_tier"))
check("refused: Anthropic overload on speed counts", F.refused(529, "overloaded", "speed") and F.refused(429, "rate limited", "speed"))
check("not refused: 400 about something else", not F.refused(400, "max_tokens too large", "speed"))
check("not refused: 429 for service_tier is a normal rate limit", not F.refused(429, "rate limited", "service_tier"))
check("not refused: success", not F.refused(200, "", "speed"))

check("ContextVar defaults to off (background runs never set it)", F.current() is False)


async def _turn():
    tok = F.use(True)
    try:
        inner = await asyncio.create_task(_peek())
        return F.current(), inner
    finally:
        F.CURRENT.reset(tok)


async def _peek():
    return F.current()

on, inner = asyncio.run(_turn())
check("a turn that turns it on sees it, and tasks it starts inherit it", on is True and inner is True)
check("after the turn it is off again", F.current() is False)

F.remember("anthropic-cli", "cooldown", "rate limit")
F.remember("openai", "fallback", "service_tier not supported")
st = F.states()
check("remembers the last state per brain", st.get("anthropic-cli", {}).get("state") == "cooldown"
      and st["anthropic-cli"].get("reason") == "rate limit" and st.get("openai", {}).get("state") == "fallback", st)
F.remember("anthropic-cli", "on")
check("a later state replaces the earlier one", F.states()["anthropic-cli"] == {"state": "on", "reason": ""}, F.states())

if fails:
    print("\nFAIL - test_fast_mode: %d" % len(fails))
    sys.exit(1)
print("\nOK - test_fast_mode: all pass")
