"""The tool-choice eval scores right and wrong answers correctly, with no API call (spec checks 19 and 20)."""

from types import SimpleNamespace as NS

from eval import tool_choice as tc


def text(t):
    return NS(type="text", text=t)


def call(name, **inp):
    return NS(type="tool_use", name=name, input=inp)


def reply(*blocks):
    usage = NS(
        input_tokens=1000,
        output_tokens=100,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
    )
    return NS(
        content=list(blocks),
        usage=usage,
        model="claude-opus-5-5",
        stop_reason="end_turn",
    )


class FakeClient:
    """Answers every prompt the right way, except the ids it is told to get wrong."""

    def __init__(self, cfg, wrong=(), unwanted=()):
        self.by_text = {p["text"]: p for p in cfg["prompts"]}
        self.wrong, self.unwanted = set(wrong), set(unwanted)
        self.beta = NS(messages=NS(create=self.create))

    def create(self, **kw):
        p = self.by_text[kw["messages"][0]["content"]]
        assert (
            kw["betas"] == ["server-side-fallback-2026-07-01"]
            and kw["fallbacks"] == "default"
        )
        if p["id"] in self.unwanted:
            return reply(call("check_lenders", companies=[{"name": "KnowBe4"}]))
        if p["kind"] == "must_not":
            return reply(text("Here you go."))
        names = p["expect"][:-1] if p["id"] in self.wrong else p["expect"]
        args = {"companies": [{"name": n} for n in names]}
        if p.get("as_of"):
            args["as_of"] = p["as_of"]
        return reply(call("check_lenders", **args))


def test_all_right_answers_pass():
    cfg = tc.load()
    r = tc.run_once(FakeClient(cfg), cfg, tc.hosted_tools(), tc.system_prompt())
    assert r.passes(True) == (20, 20) and r.passes(False) == (10, 10)
    assert tc.meets_targets(r, cfg)
    assert r.cost_usd > 0


def test_a_wrong_call_and_an_unwanted_call_fail_the_run():
    cfg = tc.load()
    fake = FakeClient(cfg, wrong={"job-3"}, unwanted={"not-4"})
    r = tc.run_once(fake, cfg, tc.hosted_tools(), tc.system_prompt())
    failed = {v.id for v in r.verdicts if not v.passed}
    assert failed == {"job-3", "not-4"}
    assert not tc.meets_targets(r, cfg)


def test_the_cli_exits_1_below_target(monkeypatch, tmp_path):
    cfg = tc.load()
    monkeypatch.setattr(
        "erm.api.default_client", lambda: FakeClient(cfg, unwanted={"not-1"})
    )
    out = tmp_path / "summary.md"
    assert tc.main(["--live", "--runs", "1", "--summary", str(out)]) == 1
    assert "API stand-in" in out.read_text() and "`not-1`" in out.read_text()


def test_a_failed_lookup_may_offer_before_running():
    p = {"id": "x", "kind": "failed_lookup", "expect": ["KnowBe4"]}
    assert tc.grade(
        p,
        [text("Lenders write names differently. Want me to run Lender Watch on them?")],
    ).passed
    assert not tc.grade(p, [text("Use TRIM on both columns.")]).passed


def test_the_quarter_is_checked_when_the_prompt_names_one():
    p = {"id": "x", "kind": "names_job", "expect": ["Anaplan"], "as_of": "2026-03-31"}
    assert not tc.grade(
        p, [call("check_lenders", companies=[{"name": "Anaplan"}])]
    ).passed
    assert tc.grade(
        p, [call("check_lenders", companies=[{"name": "anaplan"}], as_of="2026-03-31")]
    ).passed


def test_prompts_name_only_public_demo_companies_and_have_ten_must_not():
    assert tc.check_prompts(tc.load()) == []


def test_tools_sent_are_the_hosted_connector_s_own():
    tools = tc.hosted_tools()
    assert [t["name"] for t in tools] == ["check_lenders", "confirm_match"]
    assert "50 items" in tools[0]["description"]
