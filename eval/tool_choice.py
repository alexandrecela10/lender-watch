"""Tool-choice eval: does Claude pick Lender Watch when it should, and only then?

Spec: specs/engine-in-excel-and-claude.md, section 7. Sends each prompt in evals/tool_choice.yaml to the Anthropic API
with the lender-watch skill as the system prompt and the hosted connector's own tool definitions, then reads which
tool Claude asked for. It never runs a tool. It's an API stand-in for the Claude apps, which add their own
instructions. Prompts name only public demo companies. Calls Anthropic only with --live: off by default.
Prints prompt ids and verdicts only, never prompt text.

Usage:
    uv run python -m eval.tool_choice --dry-run
    uv run python -m eval.tool_choice --live [--runs 3] [--summary OUT.md]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from mcp.server.mcpserver import MCPServer

from erm import lender_tools
from erm.match.judge import cost_usd

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "evals/tool_choice.yaml"
SKILL = ROOT / ".claude/skills/lender-watch/SKILL.md"
DEMO = ROOT / "data/demo/sample_list.csv"
UNPRICED_USD = 0.05  # a call answered by a model with no known price counts this much toward the cap
HOSTED_MAX_NAMES = 50
SYSTEM_INTRO = (
    "You are Claude, helping an investment analyst who works in Excel. "
    "The analyst has connected the Lender Watch connector and its skill, below.\n\n"
)


@dataclass
class Verdict:
    id: str
    kind: str
    passed: bool
    called: list[str]
    why: str = ""


@dataclass
class RunResult:
    verdicts: list[Verdict] = field(default_factory=list)
    cost_usd: float = 0.0
    models: Counter = field(default_factory=Counter)
    errors: int = 0
    stopped: str = ""

    def passes(self, must: bool) -> tuple[int, int]:
        group = [v for v in self.verdicts if (v.kind != "must_not") == must]
        return sum(v.passed for v in group), len(group)


def load(path: Path = PROMPTS) -> dict:
    return yaml.safe_load(path.read_text())


def hosted_tools() -> list[dict]:
    """The tools exactly as the hosted connector publishes them: names, descriptions and input schemas."""
    mcp = MCPServer(lender_tools.SERVER_NAME)
    lender_tools.register(
        mcp,
        engine=lambda: None,
        owner=lambda: "eval",
        source="eval",
        max_names=HOSTED_MAX_NAMES,
    )
    tools = asyncio.run(mcp.list_tools())
    return [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in tools
    ]


def system_prompt() -> str:
    return SYSTEM_INTRO + SKILL.read_text()


def grade(p: dict, content: list) -> Verdict:
    """Pass rules: must_not, no tool at all. Others, check_lenders with exactly the expected names (and quarter).
    A failed lookup also passes when Claude names Lender Watch and offers it without calling: the skill says to ask."""
    calls = [b for b in content if getattr(b, "type", "") == "tool_use"]
    names = [c.name for c in calls]
    if p["kind"] == "must_not":
        return Verdict(
            p["id"], p["kind"], not calls, names, "" if not calls else "called a tool"
        )
    checks = [c for c in calls if c.name == "check_lenders"]
    if not checks:
        text = " ".join(
            getattr(b, "text", "") for b in content if getattr(b, "type", "") == "text"
        )
        offered = "lender watch" in text.casefold() or "check_lenders" in text
        if p["kind"] == "failed_lookup" and offered:
            return Verdict(p["id"], p["kind"], True, names, "offered before running")
        return Verdict(p["id"], p["kind"], False, names, "no check_lenders call")
    sent = {
        str(c.get("name", "")).casefold()
        for call in checks
        for c in (call.input or {}).get("companies", [])
    }
    want = {n.casefold() for n in p["expect"]}
    if sent != want:
        return Verdict(
            p["id"],
            p["kind"],
            False,
            names,
            f"names differ: {len(sent & want)} of {len(want)} right, {len(sent - want)} extra",
        )
    if p.get("as_of") and not all(
        (c.input or {}).get("as_of") == p["as_of"] for c in checks
    ):
        return Verdict(p["id"], p["kind"], False, names, "wrong or missing quarter")
    return Verdict(p["id"], p["kind"], True, names)


def ask(client, model: str, tools: list[dict], system: str, text: str):
    """One request. Fallbacks on by default, so a declined request is retried on another model and recorded."""
    return client.beta.messages.create(
        model=model,
        max_tokens=16000,
        system=[
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
        ],
        tools=tools,
        messages=[{"role": "user", "content": text}],
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )


def run_once(
    client, cfg: dict, tools: list[dict], system: str, workers: int = 5
) -> RunResult:
    out = RunResult()
    cap = float(cfg["cost_cap_usd_per_run"])

    def one(p):
        try:
            return p, ask(client, cfg["model"], tools, system, p["text"]), None
        except Exception as e:  # noqa: BLE001 - one failed call is a failed prompt, not a crashed run
            return p, None, e

    prompts = cfg["prompts"]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i in range(0, len(prompts), workers):
            if out.cost_usd >= cap:
                out.stopped = f"cost cap ${cap:.2f} reached"
                break
            for p, response, error in pool.map(one, prompts[i : i + workers]):
                if error is not None:
                    out.errors += 1
                    out.verdicts.append(
                        Verdict(
                            p["id"],
                            p["kind"],
                            False,
                            [],
                            f"API error: {type(error).__name__}",
                        )
                    )
                    continue
                cost = cost_usd(response.model, response.usage)
                out.cost_usd += UNPRICED_USD if cost is None else cost
                out.models[response.model] += 1
                if response.stop_reason == "refusal":
                    out.verdicts.append(
                        Verdict(p["id"], p["kind"], False, [], "refused")
                    )
                    continue
                out.verdicts.append(grade(p, response.content))
    return out


def meets_targets(r: RunResult, cfg: dict) -> bool:
    must_ok, must_n = r.passes(True)
    not_ok, not_n = r.passes(False)
    t = cfg["targets"]
    return (
        not r.stopped
        and must_ok >= t["must_call"]
        and must_n >= t["must_call"]
        and not_ok >= t["must_not_call"]
        and not_n >= t["must_not_call"]
    )


def summary(results: list[RunResult], cfg: dict, seconds: int) -> str:
    lines = [
        "## Tool-choice eval (API stand-in for the Claude apps)",
        "",
        f"Model `{cfg['model']}`, {len(results)} run(s), {seconds} s. Prompts written by Claude, not checked by a person.",
        "",
        "| Run | Must call | Must not call | Cost (USD) | Result |",
        "|---|---|---|---|---|",
    ]
    for i, r in enumerate(results, 1):
        mc, mn = r.passes(True)
        nc, nn = r.passes(False)
        ok = "PASS" if meets_targets(r, cfg) else "FAIL"
        lines.append(
            f"| {i} | {mc} of {mn} | {nc} of {nn} | {r.cost_usd:.2f} | {ok}{' (' + r.stopped + ')' if r.stopped else ''} |"
        )
    failed = Counter((v.id, v.why) for r in results for v in r.verdicts if not v.passed)
    if failed:
        lines += ["", "Failures (prompt id, reason, runs):"]
        lines += [f"- `{pid}`: {why} ({n})" for (pid, why), n in sorted(failed.items())]
    models = sum((r.models for r in results), Counter())
    lines += [
        "",
        "Models that answered: " + ", ".join(f"{m} ({n})" for m, n in models.items()),
    ]
    return "\n".join(lines) + "\n"


def check_prompts(cfg: dict) -> list[str]:
    """Problems with the prompt file: counts, kinds, and names that aren't in the public demo list."""
    import pandas as pd

    demo = {n.casefold() for n in pd.read_csv(DEMO).Company}
    kinds = Counter(p["kind"] for p in cfg["prompts"])
    problems = []
    if kinds["must_not"] < 10:
        problems.append(f"only {kinds['must_not']} must-not-call prompts")
    if (
        sum(v for k, v in kinds.items() if k != "must_not")
        != cfg["targets"]["must_call"]
    ):
        problems.append("must-call prompt count differs from its target")
    for p in cfg["prompts"]:
        problems += [
            f"{p['id']}: {n} is not on the demo list"
            for n in p["expect"]
            if n.casefold() not in demo
        ]
    return problems


def main(argv=None) -> int:
    a = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    mode = a.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="check the prompt file and tools; no API call",
    )
    mode.add_argument(
        "--live", action="store_true", help="call the Anthropic API (sends the prompts)"
    )
    a.add_argument("--runs", type=int)
    a.add_argument("--summary", help="write the result as markdown to this file")
    args = a.parse_args(argv)

    cfg = load()
    problems = check_prompts(cfg)
    tools = hosted_tools()
    if args.dry_run or problems:
        print(
            f"{len(cfg['prompts'])} prompts, tools: {', '.join(t['name'] for t in tools)}"
        )
        for p in problems:
            print(f"Problem: {p}")
        return 1 if problems else 0

    from erm.api import default_client

    client = default_client()
    if client is None:
        print("No ANTHROPIC_API_KEY: skipped. Nothing was sent.")
        return 0
    start = time.monotonic()
    results = []
    for i in range(args.runs or int(cfg["runs"])):
        r = run_once(client, cfg, tools, system_prompt())
        results.append(r)
        for v in r.verdicts:
            print(
                f"run {i + 1} {v.kind:15} {v.id:10} {'PASS' if v.passed else 'FAIL'} {v.why}"
            )
    text = summary(results, cfg, round(time.monotonic() - start))
    print(text)
    if args.summary:
        Path(args.summary).write_text(text)
    return 0 if all(meets_targets(r, cfg) for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
