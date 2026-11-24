"""The chat layer: a language model asks the clarifying questions and fills in a brief; advisor.py does the searching.

The model never sees the raw data and cannot invent a number: its only tool, search_homes, runs advisor.search and returns
measured results, and the browser draws the areas from that same result. Two providers are supported behind one small
interface: Google Gemini (GEMINI_API_KEY, has a free tier) and Anthropic Claude (ANTHROPIC_API_KEY). With no key the endpoint
reports "no_key" and the page falls back to a short form that calls the same engine.

Put the key in Localytics/.env yourself (never in chat or in the repo):  GEMINI_API_KEY=...   or   ANTHROPIC_API_KEY=...
Choose explicitly with ADVISOR_PROVIDER=gemini|anthropic; otherwise Gemini is used when its key is present.
"""

import json
import os
import re
import threading
import time
import uuid
from pathlib import Path

import advisor

ANTHROPIC_MODEL = os.environ.get("ADVISOR_MODEL", "claude-opus-5-5")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")  # gemini-2.5-* is closed to new accounts; others are tried if this one is gone or busy
MAX_ROUNDS = 4          # model <-> tool round trips per user message
MAX_USER_TURNS = 30     # per conversation
MAX_SESSIONS = 50
MAX_TEXT = 1500         # characters per user message

SYSTEM = """You are the Localytics housing advisor inside a map of Delhi and Gurugram buildings. You help a person decide where to live.

You do not know any rents, prices, air readings or areas yourself. Everything you say about an area must come from a search_homes result. Never invent, estimate or round up a number, and never name an area that was not in a result.

Before you search you need: rent or buy, how many bedrooms (BHK), and which city (Delhi, Gurugram or both). Also ask for a budget (monthly rent, or purchase price) unless the person says they have none.
- If something is missing, ask for it in ONE short message: at most 3 questions, each answerable in a few words. Do not search yet.
- If an answer is vague ("cheap", "nearby", "good air", "affordable"), ask for a number or a choice instead of guessing, for example "What is the most you would pay per month?".
- Never repeat a question the person has already answered. "Don't mind" or "no preference" is a valid answer: accept it.
- Optional, and only when it matters to them: where they work (a sector, colony or society name as it appears on the map) and the longest straight-line distance they would accept; how much air quality matters (none, some or high); must-haves nearby (park, metro, school, hospital, shopping) versus nice-to-haves. Ask at most one of these extra things before the first search; refine afterwards.

Facts about the data that you must respect:
- Delhi has rents only (locality medians from an open dataset collected in August 2020, so today's rents are higher). There are no Delhi sale prices. For Buy, only Gurugram can be searched.
- Gurugram has current listing medians for buying and renting.
- PM2.5 comes from the nearest monitor in one cached snapshot, within 5 km. Many Gurugram buildings have no reading; no reading means unknown, never clean. It is indicative, not an official AQI. Readings in this data are all poor to severe, so talk about better or worse relative to other areas, never "good air".
- Commute is straight-line distance, not travel time. Say so when you mention it.
- You can search by workplace only when its name matches a locality or society in the data. If the tool says it could not find it, ask the person for the nearest sector, colony or society name, and you may offer names from the tool's options list only.

After a search, reply in plain text, under 150 words, with no markdown at all (no asterisks, no tables): name the top 3 areas with their key numbers from the result (rent or price, PM2.5 and how many buildings had a reading, distance if any), state the caveats that apply, say the map now shows these areas, and end with one question that would sharpen the result (or offer to adjust budget, distance or priorities). If no area qualified, say which single constraint is binding using why_empty and ask which one to relax. If a tool error tells you to ask the user something, ask exactly that.
Keep an even tone. Do not give investment, legal or financial advice. If asked about something else, say you only help with finding areas in Delhi and Gurugram."""

# Plain JSON schema with no null unions, so both providers accept it. Optional fields are simply left out.
TOOL = {
    "name": "search_homes",
    "description": ("Search the Delhi and Gurugram buildings and rank areas. Call it only when rent/buy, bedrooms and city are known "
                    "(and a budget unless the person has none). Returns measured counts and ranked areas, or an error telling you what to ask."),
    "input_schema": {
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": ["rent", "buy"]},
            "city": {"type": "string", "enum": ["delhi", "gurugram", "both"]},
            "bhk": {"type": "array", "items": {"type": "integer"}, "description": "Bedrooms wanted, 1 to 5 (5 means 5 or more). Several allowed."},
            "budget_max": {"type": "number", "description": "Rupees: per month for rent, total for buy. Leave out when the person has no limit."},
            "kinds": {"type": "array", "items": {"type": "string", "enum": list(advisor.KINDS)}, "description": "Defaults to apartments and builder floors."},
            "workplace": {"type": "string", "description": "A locality or society name as on the map. Leave out when not given."},
            "max_commute_km": {"type": "number", "description": "Longest straight-line distance to the workplace. Leave out when not given."},
            "air_priority": {"type": "string", "enum": ["none", "some", "high"]},
            "must_be_near": {"type": "array", "items": {"type": "string", "enum": list(advisor.NEAR)}, "description": "Hard requirements: park 500 m, metro 1.5 km, school 1 km, hospital 2 km, shopping 1.5 km."},
            "nice_to_have": {"type": "array", "items": {"type": "string", "enum": list(advisor.NEAR)}, "description": "Preferences that only change the ranking."},
        },
        "required": ["mode", "city", "bhk"],
    },
}


class ChatError(Exception):
    """A failure the page can show: .code is no_key, offline, refused, busy, limit or error."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


class Call:
    def __init__(self, id, name, args):
        self.id, self.name, self.args = id, name, args


class Turn:
    """One model reply in provider-neutral form. `raw` is what goes back into the history unchanged."""

    def __init__(self, text="", calls=(), raw=None, refused=False):
        self.text, self.calls, self.raw, self.refused = text, list(calls), raw, refused


def load_keys(localytics_dir):
    """Read Localytics/.env (python-dotenv) into the environment. Returns which provider keys are present."""
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(localytics_dir) / ".env")
    except Exception:  # dotenv is optional here
        pass
    return dict(
        gemini=bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
        anthropic=bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")),
    )


# ---------- Anthropic Claude ----------
class AnthropicBackend:
    name = "anthropic"

    def __init__(self, client=None):
        self._client = client
        self._fallbacks = True  # server-side refusal fallback; switched off if the API rejects it
        self.model_name = ANTHROPIC_MODEL

    def user(self, text):
        return {"role": "user", "content": text}

    def generate(self, messages):
        import anthropic
        client = self._client or anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
        args = dict(model=self.model_name, max_tokens=2500, system=SYSTEM, tools=[TOOL], messages=messages,
                    thinking={"type": "adaptive"}, output_config={"effort": "low"})
        try:
            response = self._create(client, anthropic, args)
        except anthropic.AuthenticationError:
            raise ChatError("no_key", "The Anthropic API key was not accepted. Check ANTHROPIC_API_KEY in Localytics/.env.") from None
        except anthropic.RateLimitError:
            raise ChatError("busy", "The assistant is busy right now. Try again in a moment, or use the quick form.") from None
        except (anthropic.APIConnectionError, anthropic.APITimeoutError):
            raise ChatError("offline", "Could not reach the assistant (no internet?). Use the quick form instead.") from None
        except anthropic.APIStatusError as exc:
            raise ChatError("error", f"The assistant service returned an error ({exc.status_code}). Use the quick form instead.") from None
        calls = [Call(b.id, b.name, dict(b.input or {})) for b in response.content if b.type == "tool_use"]
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        return Turn(text, calls if response.stop_reason == "tool_use" else [], raw=response.content, refused=response.stop_reason == "refusal")

    def _create(self, client, anthropic, args):
        if self._fallbacks:
            try:
                return client.beta.messages.create(**args, betas=["server-side-fallback-2026-07-01"], fallbacks="default")
            except anthropic.BadRequestError as exc:
                if "fallback" not in str(exc).lower():
                    raise
                self._fallbacks = False  # this account or platform does not take the parameter: carry on without it
        return client.beta.messages.create(**args)

    def add_reply(self, messages, turn):
        messages.append({"role": "assistant", "content": turn.raw})

    def add_results(self, messages, turn, results):
        messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": call.id, "content": content, **({"is_error": True} if is_error else {})}
            for call, content, is_error in results]})


# ---------- Google Gemini ----------
NOT_MODEL = re.compile(r"preview|exp|tts|image|live|audio|embed|vision|thinking|robotics|computer|customtools|latest|\d{3}$", re.I)
TRY_NEXT = (404, 429, 500, 502, 503, 504)  # this model cannot answer right now: try another one
OVERLOADED = (500, 502, 503, 504)         # transient: worth one retry on the same model
MAX_MODELS = 4
CALL_TIMEOUT_MS = 10000                    # Google can take ~9 s just to say 'overloaded'
TOTAL_BUDGET_S = 25                         # stop trying other models after this long; the page then offers the form


class GeminiBackend:
    name = "gemini"

    def __init__(self, client=None):
        self._client = client
        self.model_name = GEMINI_MODEL

    def _types(self):
        from google.genai import types
        return types

    def _make_client(self):
        from google import genai
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        base = os.environ.get("GEMINI_BASE_URL")  # for testing or a proxy
        types = self._types()
        # One attempt per call and a 10 s limit per call: this class does its own retrying and model switching (the SDK's own
        # retries back off for minutes when Google is overloaded, which would leave the chat hanging).
        options = types.HttpOptions(base_url=base, timeout=CALL_TIMEOUT_MS, retry_options=types.HttpRetryOptions(attempts=1))
        return genai.Client(api_key=key, http_options=options)

    def user(self, text):
        t = self._types()
        return t.Content(role="user", parts=[t.Part(text=text)])

    def _schema(self, js):
        """The tool's JSON schema as a google-genai Schema (the long-supported route for function declarations)."""
        t = self._types()
        kw = dict(type=js["type"].upper())
        for key in ("description", "enum", "required"):
            if key in js:
                kw[key] = js[key]
        if "properties" in js:
            kw["properties"] = {k: self._schema(v) for k, v in js["properties"].items()}
        if "items" in js:
            kw["items"] = self._schema(js["items"])
        return t.Schema(**kw)

    def _config(self):
        t = self._types()
        return t.GenerateContentConfig(
            system_instruction=SYSTEM, temperature=0.3, max_output_tokens=4096,
            tools=[t.Tool(function_declarations=[t.FunctionDeclaration(name=TOOL["name"], description=TOOL["description"], parameters=self._schema(TOOL["input_schema"]))])],
            automatic_function_calling=t.AutomaticFunctionCallingConfig(disable=True))  # our loop runs the tool, not the SDK

    def generate(self, messages):
        from google.genai import errors
        client = self._client or self._make_client()
        try:
            response = self._generate(client, messages, errors)
        except errors.APIError as exc:
            text = str(exc).lower()
            if exc.code in (401, 403) or (exc.code == 400 and "api key" in text):
                raise ChatError("no_key", "The Gemini API key was not accepted. Check GEMINI_API_KEY in Localytics/.env.") from None
            if exc.code == 429:
                raise ChatError("busy", "The Gemini free quota is used up for now. Try again in a minute, or use the quick form.") from None
            if exc.code in OVERLOADED:
                raise ChatError("busy", "Google's Gemini servers report high demand right now. Try again in a minute, or use the quick form.") from None
            if exc.code == 404:
                raise ChatError("error", f"No Gemini model your key can use was found (last tried '{self.model_name}'). Set GEMINI_MODEL in Localytics/.env.") from None
            raise ChatError("error", f"The assistant service returned an error ({exc.code}). Use the quick form instead.") from None
        except ChatError:
            raise
        except Exception as exc:  # connection and timeout errors come from the HTTP library, not the SDK
            if type(exc).__module__.split(".")[0] in ("httpx", "httpx2", "httpcore", "httpcore2", "requests", "urllib3", "socket", "ssl") or isinstance(exc, OSError):
                raise ChatError("offline", "Could not reach the assistant (no internet?). Use the quick form instead.") from None
            raise
        return self._turn(response)

    def _generate(self, client, messages, errors):
        """Call the model; on a retired model, an overload or a quota limit, retry once and then try other Flash models."""
        queue, tried, listed, last = [self.model_name], [], False, None
        deadline = time.monotonic() + TOTAL_BUDGET_S
        while queue and len(tried) < MAX_MODELS and (not tried or time.monotonic() < deadline):
            model = queue.pop(0)
            tried.append(model)
            for attempt in range(2):
                started = time.monotonic()
                try:
                    response = client.models.generate_content(model=model, contents=messages, config=self._config())
                    self.model_name = model  # stay on the model that worked
                    return response
                except errors.APIError as exc:
                    last = exc
                    quick = time.monotonic() - started < 4  # an instant 503 is worth a second try; a slow one means "busy"
                    if exc.code in OVERLOADED and attempt == 0 and quick:
                        time.sleep(1.5)
                        continue
                    break
            if last.code not in TRY_NEXT:
                raise last
            if not listed:
                listed = True
                queue += [m for m in self._candidates(client) if m not in tried and m not in queue]
        raise last

    def _candidates(self, client):
        """Stable Flash models this key can call with generateContent: the newest, then the newest 'lite', then the rest."""
        found = []
        try:
            for m in client.models.list():
                name = (m.name or "").removeprefix("models/")
                if "flash" in name and not NOT_MODEL.search(name) and "generateContent" in (m.supported_actions or []):
                    found.append(name)
        except Exception:  # listing is a nicety: without it we just keep to the chosen model
            return []
        newest = lambda n: [-int(x) for x in re.findall(r"\d+", n)]  # noqa: E731
        full, light = sorted((n for n in found if "lite" not in n), key=newest), sorted((n for n in found if "lite" in n), key=newest)
        return full[:1] + light[:1] + full[1:] + light[1:]  # the lighter models are usually less busy: try one early

    def _turn(self, response):
        candidate = (response.candidates or [None])[0]
        content = candidate.content if candidate else None
        parts = (content.parts if content else None) or []
        blocked = bool(getattr(response, "prompt_feedback", None) and getattr(response.prompt_feedback, "block_reason", None))
        if blocked or not parts:
            reason = str(getattr(candidate, "finish_reason", "") or "")
            return Turn(refused=blocked or any(w in reason for w in ("SAFETY", "PROHIBITED", "BLOCKLIST", "SPII")), raw=content)
        calls = [Call(p.function_call.id, p.function_call.name, dict(p.function_call.args or {})) for p in parts if p.function_call]  # Gemini often sends no id
        text = "".join(p.text for p in parts if p.text and not p.thought).strip()
        return Turn(text, calls, raw=content)

    def add_reply(self, messages, turn):
        if turn.raw is not None:
            messages.append(turn.raw)  # unchanged, so Gemini's thought signatures stay attached

    def add_results(self, messages, turn, results):
        t = self._types()
        parts = []
        for call, content, is_error in results:
            body = {"error": content} if is_error else {"result": json.loads(content)}
            parts.append(t.Part(function_response=t.FunctionResponse(id=call.id, name=call.name, response=body)))
        messages.append(t.Content(role="user", parts=parts))


def make_backend(localytics_dir):
    """Pick the provider: ADVISOR_PROVIDER if set, else Gemini when its key is present, else Claude. None when there is no key."""
    keys = load_keys(localytics_dir)
    want = os.environ.get("ADVISOR_PROVIDER", "").lower()
    if want == "anthropic" and keys["anthropic"]:
        return AnthropicBackend()
    if want == "gemini" and keys["gemini"]:
        return GeminiBackend()
    if keys["gemini"]:
        return GeminiBackend()
    if keys["anthropic"]:
        return AnthropicBackend()
    return None


class Advisor:
    def __init__(self, localytics_dir, data_path=advisor.DATA, client=None, backend=None):
        self.data_path = data_path
        self.backend = backend or (AnthropicBackend(client) if client else make_backend(localytics_dir))
        self.sessions = {}
        self.lock = threading.Lock()

    # -- status and sessions --
    def status(self):
        b = self.backend
        return dict(llm=b is not None, provider=b.name if b else None, model=b.model_name if b else None)

    def _session(self, sid):
        with self.lock:
            if sid not in self.sessions:
                if len(self.sessions) >= MAX_SESSIONS:
                    oldest = min(self.sessions, key=lambda k: self.sessions[k]["touched"])
                    del self.sessions[oldest]
                self.sessions[sid] = dict(messages=[], turns=0, lock=threading.Lock(), touched=time.time())
            s = self.sessions[sid]
            s["touched"] = time.time()
            return s

    def reset(self, sid):
        with self.lock:
            self.sessions.pop(sid, None)

    # -- one user message --
    def chat(self, sid, text):
        text = (text or "").strip()
        if not text:
            raise ChatError("error", "Type a message first.")
        if self.backend is None:
            raise ChatError("no_key", "The chat needs an API key. Add GEMINI_API_KEY (free tier) or ANTHROPIC_API_KEY to Localytics/.env and restart the data service, or use the quick form.")
        sid = sid or uuid.uuid4().hex
        session = self._session(sid)
        with session["lock"]:
            if session["turns"] >= MAX_USER_TURNS:
                raise ChatError("limit", "This conversation is long enough: start a new chat.")
            messages, mark = session["messages"], len(session["messages"])
            messages.append(self.backend.user(text[:MAX_TEXT]))
            session["turns"] += 1
            try:
                return dict(session=sid, **self._run(messages))
            except BaseException:
                del messages[mark:]  # a failed turn leaves the conversation as it was
                session["turns"] -= 1
                raise

    def _run(self, messages):
        b, search, turn = self.backend, None, None
        for _ in range(MAX_ROUNDS):
            turn = b.generate(messages)
            if turn.refused:
                raise ChatError("refused", "The assistant declined to answer that. Try rephrasing, or use the quick form.")
            b.add_reply(messages, turn)
            if not turn.calls:
                break
            results = []
            for call in turn.calls:
                content, is_error, found = self._tool(call)
                search = found or search
                results.append((call, content, is_error))
            b.add_results(messages, turn, results)
        else:
            turn = None  # the model kept calling the tool: stop and say so
        reply = turn.text if turn else ""
        if not reply:
            reply = "I found results, but could not put them into words. The areas are on the map." if search else "Sorry, I could not work that out. Please try again."
        return dict(reply=reply, search=search)

    def _tool(self, call):
        """Run one search_homes call. Returns (tool_result text, is_error, full result for the page or None)."""
        if call.name != "search_homes":
            return f"Unknown tool {call.name}", True, None
        try:
            result = advisor.search(dict(call.args or {}), path=self.data_path)
        except advisor.BriefError as exc:
            return str(exc), True, None
        return json.dumps(advisor.for_model(result), ensure_ascii=False, default=str), False, result
