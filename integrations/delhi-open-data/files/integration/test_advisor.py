"""Tests for the chat advisor: engine, parity with the map's JS filters, and the chat loop (with a fake model client).

Run from flat-finder-localytics:  <python> -m pytest integration/test_advisor.py -q
The parity test needs Node (already required for the web app) and the built web/public/data/ncr.json.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import advisor  # noqa: E402
import advisor_chat  # noqa: E402

pytestmark = pytest.mark.skipif(not advisor.DATA.exists(), reason="build web/public/data/ncr.json first")

BRIEFS = [
    dict(mode="rent", bhk=[3], city="both"),
    dict(mode="rent", bhk=[2], city="delhi", budget_max=30000, must_be_near=["metro"]),
    dict(mode="rent", bhk=[3], city="gurugram", budget_max=60000, workplace="Golf Course Road", max_commute_km=8),
    dict(mode="buy", bhk=[3, 4], city="both", budget_max=30000000, kinds=["apartment"]),
    dict(mode="rent", bhk=[5], city="both", budget_max=150000),
    dict(mode="rent", bhk=[1], city="delhi", kinds=["apartment"], must_be_near=["park", "school"]),
    dict(mode="buy", bhk=[2], city="gurugram"),
]


def test_counts_equal_the_map_filter_panel():
    """The number the chat reports must equal the number the filter panel shows for the criteria the chat sets."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node not found")
    data = advisor.load()
    criteria = []
    for brief in BRIEFS:
        c, extra = advisor.normalise(brief)
        if extra["workplace"]:
            place = advisor.resolve_place(data, extra["workplace"])
            c["commute"] = dict(lat=place["lat"], lng=place["lng"], km=float(extra["max_commute_km"]))
        criteria.append(c)
    scratch = HERE / "_parity_criteria.json"
    scratch.write_text(json.dumps(criteria))
    try:
        out = subprocess.run([node, str(HERE / "count_js.mjs"), str(advisor.DATA), str(scratch)], capture_output=True, text=True, check=True, timeout=120).stdout
    finally:
        scratch.unlink(missing_ok=True)
    js = json.loads(out)
    for brief, c, ids in zip(BRIEFS, criteria, js):
        py = sorted(s["id"] for s in data["societies"] if advisor.state(s, c) == "match")
        assert py == ids, f"{brief}: python {len(py)} vs js {len(ids)}"
        assert advisor.search(brief)["counts"]["matched"] == len(ids)


def test_missing_fields_are_reported():
    with pytest.raises(advisor.BriefError, match="bhk"):
        advisor.search(dict(mode="rent", city="delhi"))
    with pytest.raises(advisor.BriefError, match="mode"):
        advisor.search(dict(bhk=[2], city="delhi"))
    with pytest.raises(advisor.BriefError, match="no sale prices"):
        advisor.search(dict(mode="buy", bhk=[2], city="delhi"))


def test_unknown_workplace_asks_for_a_nearby_name():
    with pytest.raises(advisor.BriefError, match="nearest sector, colony or society"):
        advisor.search(dict(mode="rent", bhk=[2], city="both", workplace="Zzyzx Plaza", max_commute_km=5))


def test_workplace_resolves_from_the_data_not_from_memory():
    place = advisor.resolve_place(advisor.load(), "Golf Course Road")
    assert place["status"] == "found" and place["city"] == "Gurugram"
    assert 28.3 < place["lat"] < 28.6 and 76.9 < place["lng"] < 77.2


def test_a_budget_excludes_buildings_with_no_price():
    """Without a price a building cannot be shown to fit a budget (strictPrice), in Gurugram as well as Delhi."""
    data = advisor.load()
    c, _ = advisor.normalise(dict(mode="rent", bhk=[3], city="gurugram", budget_max=5000))
    for s in data["societies"]:
        if advisor.state(s, c) == "match":
            assert advisor.price_for(s, "rent", c["bhk"]) is not None


def test_both_cities_are_ranked_separately():
    result = advisor.search(dict(mode="rent", bhk=[3], city="both", budget_max=60000))
    cities = {a["city"] for a in result["areas"]}
    assert cities == {"Delhi", "Gurugram"}
    assert any("August 2020" in w for w in result["warnings"])
    assert all(a["name"] for a in result["areas"])  # never an area with an empty name
    assert all(a["n"] >= advisor.MIN_AREA_BUILDINGS for a in result["areas"])


def test_missing_pm25_is_unknown_never_clean():
    result = advisor.search(dict(mode="rent", bhk=[3], city="gurugram", air_priority="high"))
    bare = [a for a in result["areas"] if not a["pm25"].get("known")]
    for a in bare:
        assert a["parts"].get("air") == 0.25
        assert "no PM2.5 reading nearby" in a["reasons"]


def test_empty_result_explains_which_constraint_binds():
    result = advisor.search(dict(mode="rent", bhk=[3], city="gurugram", budget_max=1000))
    assert result["areas"] == []
    assert "budget_max" in result["why_empty"]["matches_if_dropped"]
    assert result["why_empty"]["cheapest_available"] > 1000


# ---------- the chat loop, with a fake model ----------
def block(kind, **kw):
    return SimpleNamespace(type=kind, **kw)


class FakeClient:
    """Stands in for anthropic.Anthropic: replays scripted responses and records what it was sent."""

    def __init__(self, script):
        self.script, self.calls = list(script), []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kw):
        self.calls.append(json.loads(json.dumps(kw, default=lambda o: getattr(o, "__dict__", str(o)))))
        return self.script.pop(0)


def text(t):
    return SimpleNamespace(stop_reason="end_turn", content=[block("text", text=t)])


def call(**inp):
    return SimpleNamespace(stop_reason="tool_use", content=[block("tool_use", id="tu_1", name="search_homes", input=inp)])


def make(script):
    bot = advisor_chat.Advisor(HERE, client=FakeClient(script))
    return bot, bot.backend._client


def test_vague_message_gets_a_question_and_no_search():
    bot, client = make([text("Rent or buy, how many bedrooms and which city? What is the most you would pay per month?")])
    out = bot.chat("s1", "I want a nice place")
    assert out["search"] is None and "?" in out["reply"]
    assert client.calls[0]["tools"][0]["name"] == "search_homes"
    assert "Never invent" in client.calls[0]["system"]


def test_complete_message_returns_areas_and_the_page_gets_the_full_result():
    bot, client = make([call(mode="rent", city="both", bhk=[3], budget_max=60000), text("Top areas are ...")])
    out = bot.chat("s2", "3 BHK rent in Delhi or Gurugram under 60k")
    assert out["reply"] == "Top areas are ..." and out["search"]["areas"] and out["search"]["criteria"]["maxRent"] == 60000
    assert out["search"]["areas"][0]["ids"]  # the page highlights buildings by id
    sent = client.calls[1]["messages"][-1]["content"][0]  # the tool result that went back to the model
    assert sent["type"] == "tool_result" and "ids" not in json.loads(sent["content"])["areas"][0]


def test_incomplete_tool_call_comes_back_as_an_error_the_model_must_ask_about():
    bot, client = make([call(mode="rent", city="delhi"), text("How many bedrooms do you need?")])
    out = bot.chat("s3", "rent in Delhi")
    result = client.calls[1]["messages"][-1]["content"][0]
    assert result["is_error"] and "bhk" in result["content"] and out["search"] is None


def clear_keys(monkeypatch):
    for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ADVISOR_PROVIDER"):
        monkeypatch.delenv(k, raising=False)


def test_no_key_reports_cleanly(monkeypatch):
    clear_keys(monkeypatch)
    bot = advisor_chat.Advisor(HERE)
    assert bot.status()["llm"] is False
    with pytest.raises(advisor_chat.ChatError) as e:
        bot.chat("s4", "hello")
    assert e.value.code == "no_key" and "GEMINI_API_KEY" in e.value.message


def test_provider_choice(monkeypatch):
    clear_keys(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    assert advisor_chat.make_backend(HERE).name == "anthropic"
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    assert advisor_chat.make_backend(HERE).name == "gemini"  # Gemini first when both are set (it has a free tier)
    monkeypatch.setenv("ADVISOR_PROVIDER", "anthropic")
    assert advisor_chat.make_backend(HERE).name == "anthropic"
    monkeypatch.setenv("GOOGLE_API_KEY", "g")
    monkeypatch.delenv("GEMINI_API_KEY")
    monkeypatch.setenv("ADVISOR_PROVIDER", "gemini")
    assert advisor_chat.make_backend(HERE).name == "gemini"


def test_refusal_is_reported_and_the_conversation_is_left_unchanged():
    bot, _ = make([SimpleNamespace(stop_reason="refusal", content=[])])
    with pytest.raises(advisor_chat.ChatError) as e:
        bot.chat("s5", "hi")
    assert e.value.code == "refused" and bot.sessions["s5"]["messages"] == [] and bot.sessions["s5"]["turns"] == 0


def test_runaway_tool_loop_is_capped():
    bot, client = make([call(mode="rent", city="delhi")] * advisor_chat.MAX_ROUNDS)
    out = bot.chat("s6", "rent in Delhi")
    assert len(client.calls) == advisor_chat.MAX_ROUNDS and out["reply"]


def test_conversation_is_append_only_across_turns():
    bot, client = make([text("Which city?"), text("And your budget?")])
    bot.chat("s7", "2 BHK")
    bot.chat("s7", "Delhi")
    first, second = client.calls[0]["messages"], client.calls[1]["messages"]
    assert second[: len(first)] == first or [m["role"] for m in second][:2] == ["user", "assistant"]
    assert [m["role"] for m in second] == ["user", "assistant", "user"]


# ---------- the same chat loop on Gemini, with a fake client (real google-genai types) ----------
gtypes = pytest.importorskip("google.genai.types")


class FakeGemini:
    def __init__(self, script):
        self.script, self.calls = list(script), []
        self.models = SimpleNamespace(generate_content=self.generate_content)

    def generate_content(self, model, contents, config):
        self.calls.append(dict(model=model, contents=list(contents), config=config))
        return self.script.pop(0)


def greply(*parts, finish="STOP"):
    return SimpleNamespace(candidates=[SimpleNamespace(content=gtypes.Content(role="model", parts=list(parts)), finish_reason=finish)], prompt_feedback=None)


def gtext(t):
    return greply(gtypes.Part(text=t))


def gcall(**args):
    return greply(gtypes.Part(function_call=gtypes.FunctionCall(name="search_homes", args=args)))


def gemini(script):
    fake = FakeGemini(script)
    return advisor_chat.Advisor(HERE, backend=advisor_chat.GeminiBackend(client=fake)), fake


def test_gemini_vague_message_gets_a_question_and_no_search():
    bot, fake = gemini([gtext("Rent or buy, how many bedrooms and which city?")])
    out = bot.chat("g1", "I want a nice place")
    assert out["search"] is None and "?" in out["reply"]
    cfg = fake.calls[0]["config"]
    assert cfg.tools[0].function_declarations[0].name == "search_homes"
    assert cfg.automatic_function_calling.disable is True and "Never invent" in cfg.system_instruction
    assert bot.status()["provider"] == "gemini"


def test_gemini_full_request_searches_and_feeds_the_result_back():
    bot, fake = gemini([gcall(mode="rent", city="both", bhk=[3.0], budget_max=60000.0), gtext("Top areas ...")])
    out = bot.chat("g2", "3 BHK rent in both cities under 60k")
    assert out["reply"] == "Top areas ..." and out["search"]["criteria"]["maxRent"] == 60000 and out["search"]["areas"][0]["ids"]
    sent = fake.calls[1]["contents"][-1]
    assert sent.role == "user" and sent.parts[0].function_response.name == "search_homes"
    assert "ids" not in sent.parts[0].function_response.response["result"]["areas"][0]


def test_gemini_incomplete_call_comes_back_as_an_error_to_ask_about():
    bot, fake = gemini([gcall(mode="rent", city="delhi"), gtext("How many bedrooms?")])
    out = bot.chat("g3", "rent in Delhi")
    assert "bhk" in fake.calls[1]["contents"][-1].parts[0].function_response.response["error"] and out["search"] is None


def test_gemini_blocked_reply_is_reported_and_history_restored():
    blocked = SimpleNamespace(candidates=[], prompt_feedback=SimpleNamespace(block_reason="SAFETY"))
    bot, _ = gemini([blocked])
    with pytest.raises(advisor_chat.ChatError) as e:
        bot.chat("g4", "hi")
    assert e.value.code == "refused" and bot.sessions["g4"]["messages"] == []


def test_gemini_history_keeps_the_model_content_unchanged():
    bot, fake = gemini([gtext("Which city?"), gtext("And your budget?")])
    bot.chat("g5", "2 BHK")
    bot.chat("g5", "Delhi")
    roles = [c.role for c in fake.calls[1]["contents"]]
    assert roles == ["user", "model", "user"]
    assert fake.calls[1]["contents"][1] is bot.sessions["g5"]["messages"][1]


def gemini_errors():
    return pytest.importorskip("google.genai.errors")


class Flaky(FakeGemini):
    """Fails per model with the given error code (a list is consumed one call at a time), else answers."""

    def __init__(self, script, fails):
        super().__init__(script)
        self.fails, self.tried = fails, []
        self.models.list = lambda: [SimpleNamespace(name=n, supported_actions=["generateContent"]) for n in
                                    ("models/gemini-2.5-flash-lite", "models/gemini-3.1-flash", "models/gemini-3.5-flash-preview", "models/gemini-3.2-flash", "models/gemini-3.5-pro", "models/gemini-3.4-flash-image", "models/gemini-3.3-flash-lite")]

    def generate_content(self, model, contents, config):
        self.tried.append(model)
        codes = self.fails.get(model)
        if codes:
            code = codes.pop(0) if isinstance(codes, list) else codes
            raise gemini_errors().APIError(code, {"error": {"message": "x", "code": code}})
        return super().generate_content(model, contents, config)


def flaky_bot(fails, reply="Hello, what do you need?"):
    fake = Flaky([gtext(reply)], fails)
    bot = advisor_chat.Advisor(HERE, backend=advisor_chat.GeminiBackend(client=fake))
    bot.backend.model_name = "gemini-2.5-flash"
    return bot, fake


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(advisor_chat.time, "sleep", lambda s: None)


def test_gemini_model_is_found_when_the_default_is_gone():
    bot, fake = flaky_bot({"gemini-2.5-flash": 404})
    assert bot.chat("g6", "hi")["reply"].startswith("Hello") and fake.tried == ["gemini-2.5-flash", "gemini-3.2-flash"] and bot.status()["model"] == "gemini-3.2-flash"


def test_gemini_overload_is_retried_once_on_the_same_model():
    bot, fake = flaky_bot({"gemini-2.5-flash": [503]})
    assert bot.chat("g7", "hi")["reply"] and fake.tried == ["gemini-2.5-flash", "gemini-2.5-flash"]


def test_gemini_persistent_overload_moves_to_the_next_model_newest_then_a_lite_one():
    bot, fake = flaky_bot({"gemini-2.5-flash": 503, "gemini-3.2-flash": 503})
    assert bot.chat("g8", "hi")["reply"] and fake.tried == ["gemini-2.5-flash", "gemini-2.5-flash", "gemini-3.2-flash", "gemini-3.2-flash", "gemini-3.3-flash-lite"]


def test_gemini_slow_overload_is_not_retried_on_the_same_model(monkeypatch):
    ticks = iter(range(0, 1000, 6))  # each call "takes" 6 s of the clock
    monkeypatch.setattr(advisor_chat.time, "monotonic", lambda: next(ticks))
    bot, fake = flaky_bot({"gemini-2.5-flash": 503})
    assert bot.chat("g12", "hi")["reply"] and fake.tried == ["gemini-2.5-flash", "gemini-3.2-flash"]


def test_gemini_gives_up_when_the_time_budget_is_spent(monkeypatch):
    ticks = iter(range(0, 1000, 12))
    monkeypatch.setattr(advisor_chat.time, "monotonic", lambda: next(ticks))
    bot, fake = flaky_bot({m: 503 for m in ("gemini-2.5-flash", "gemini-3.2-flash", "gemini-3.3-flash-lite", "gemini-3.1-flash")})
    with pytest.raises(advisor_chat.ChatError) as e:
        bot.chat("g13", "hi")
    assert e.value.code == "busy" and len(set(fake.tried)) < advisor_chat.MAX_MODELS


def test_gemini_all_models_overloaded_says_busy_and_keeps_the_chat_mode():
    bot, fake = flaky_bot({m: 503 for m in ("gemini-2.5-flash", "gemini-3.2-flash", "gemini-3.1-flash", "gemini-3.3-flash-lite")})
    with pytest.raises(advisor_chat.ChatError) as e:
        bot.chat("g9", "hi")
    assert e.value.code == "busy" and "high demand" in e.value.message and len(set(fake.tried)) == advisor_chat.MAX_MODELS


def test_gemini_quota_on_every_model_says_so():
    bot, _ = flaky_bot({m: 429 for m in ("gemini-2.5-flash", "gemini-3.2-flash", "gemini-3.1-flash", "gemini-3.3-flash-lite")})
    with pytest.raises(advisor_chat.ChatError) as e:
        bot.chat("g10", "hi")
    assert e.value.code == "busy" and "quota" in e.value.message


def test_gemini_bad_key_is_not_retried():
    bot, fake = flaky_bot({"gemini-2.5-flash": 403})
    with pytest.raises(advisor_chat.ChatError) as e:
        bot.chat("g11", "hi")
    assert e.value.code == "no_key" and fake.tried == ["gemini-2.5-flash"]


def test_one_city_with_no_match_near_the_workplace_is_explained():
    result = advisor.search(dict(mode="rent", bhk=[3], city="both", budget_max=60000, workplace="Golf Course Road", max_commute_km=8))
    assert any("No Delhi building matches within 8 km of Golf Course Road" in w for w in result["warnings"])
