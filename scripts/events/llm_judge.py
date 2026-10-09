#!/usr/bin/env python3
"""Offline relevance judge for event dossiers, through the BullsAI model gateway (OpenAI-compatible).

For one event and a batch of passages the model says, per passage, whether it narrates or
directly describes THIS event ('yes'), only refers to it ('mention'), or is about something else
('no'). Judgements are cached in a SQLite file, so a rerun costs nothing and the cache is the
record of what the model said.

The API key is read from the environment (BULLSAI_API_KEY) or from ~/.config/tesserae/bullsai.env.
It is never printed or logged.
"""
import json, os, re, sqlite3, sys, threading, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor

GATEWAY = os.environ.get("BULLSAI_URL", "https://gateway.bullsai.buffalo.edu")
DEFAULT_MODEL = "Qwen/Qwen3.8-27B-FP8"
PROMPT_VERSION = "v1"
# extra request fields per model, as the existing scripts use them (research/bullsai/tessa/ask_models.py)
MODEL_EXTRA = {
    "Qwen/Qwen3.8-27B-FP8": {"chat_template_kwargs": {"enable_thinking": False}},
    "openai/gpt-oss-120b": {"reasoning_effort": "low"},
}
LABEL_RANK = {"yes": 0, "mention": 1, "no": 2}

SYSTEM = (
    "You are a historian of the ancient world who reads Greek and Latin. You are given one historical "
    "EVENT (a battle, siege or treaty) with its date, place, participants and a short encyclopedia "
    "summary, and then numbered PASSAGES from ancient texts, each with an index description and some of "
    "its lines in the original language (and an English translation when one exists). For each passage "
    "decide whether it is about THIS event.\n"
    "yes: the passage narrates or directly describes this event, including its course, its immediate "
    "preparation or its outcome as part of the same narrative.\n"
    "mention: the passage refers to this event by name or by unmistakable allusion, but is about something "
    "else.\n"
    "no: the passage is about something else, including other battles, the same people or places on "
    "other occasions, and passages that only share names or vocabulary with the event. A passage with the "
    "same participants in a different year is 'no'.\n"
    "Judge only what the passage shows. Reply with JSON only, a list with one object per passage: "
    '[{"n": 1, "label": "yes|mention|no"}, ...].'
)


def load_key():
    k = os.environ.get("BULLSAI_API_KEY")
    if k:
        return k
    p = os.path.expanduser("~/.config/tesserae/bullsai.env")
    for line in open(p):
        if line.startswith("BULLSAI_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("BULLSAI_API_KEY not found in the environment or ~/.config/tesserae/bullsai.env")


def event_header(ev):
    """ev: dict with name, date, place, participants (list), intro."""
    return (f"EVENT: {ev['name']}\nDate: {ev['date']}\nPlace: {ev['place']}\n"
            f"Participants: {ev['participants']}\nSummary: {ev['intro']}\n")


def passage_block(n, p):
    """p: dict with ref, language, gist, lines [(ref, text)], translation."""
    out = [f"PASSAGE {n} [{p['ref']}, {p['language']}]"]
    if p.get("gist"):
        out.append("Index description: " + p["gist"])
    for ref, text in p.get("lines", [])[:3]:
        out.append(f"{ref}: {text}")
    if p.get("translation"):
        out.append("English translation: " + p["translation"])
    return "\n".join(out)


def parse_labels(content, n):
    got = {}
    for m in re.finditer(r'"n"\s*:\s*(\d+)\s*,\s*"label"\s*:\s*"(yes|mention|no)"', content or "", re.I):
        got[int(m.group(1))] = m.group(2).lower()
    return [got.get(i + 1) for i in range(n)]


class Judge:
    def __init__(self, model=DEFAULT_MODEL, cache_path="llm_judgements.sqlite", workers=4, batch=10, timeout=240):
        self.model, self.workers, self.batch, self.timeout = model, workers, batch, timeout
        self.key = load_key()
        self.db = sqlite3.connect(cache_path, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS judgements (model TEXT, event TEXT, window_id TEXT, prompt TEXT, "
                        "label TEXT, ts REAL, PRIMARY KEY (model, event, window_id, prompt))")
        self.db.execute("CREATE TABLE IF NOT EXISTS requests (model TEXT, event TEXT, n INTEGER, seconds REAL, "
                        "prompt_tokens INTEGER, completion_tokens INTEGER, status TEXT, ts REAL)")
        self.db.commit()
        self.lock = threading.RLock()
        self.n_requests = self.n_cached = 0

    def cached(self, event, wid):
        with self.lock:
            return self._cached(event, wid)

    def _cached(self, event, wid):
        r = self.db.execute("SELECT label FROM judgements WHERE model=? AND event=? AND window_id=? AND prompt=?",
                            (self.model, event, wid, PROMPT_VERSION)).fetchone()
        return r[0] if r else None

    def _call(self, system, user):
        body = {"model": self.model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "temperature": 0, "max_tokens": 700}
        body.update(MODEL_EXTRA.get(self.model, {}))
        data = json.dumps(body).encode()
        last = None
        for attempt in range(6):
            t0 = time.time()
            try:
                req = urllib.request.Request(GATEWAY + "/v1/chat/completions", data=data,
                                             headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    j = json.load(r)
                return j["choices"][0]["message"].get("content") or "", j.get("usage") or {}, time.time() - t0, "ok"
            except urllib.error.HTTPError as e:
                last = f"http {e.code}"
                if e.code in (429, 500, 502, 503, 504):
                    time.sleep(min(60, 4 * (attempt + 1)))
                    continue
                raise
            except Exception as e:  # timeouts, resets
                last = type(e).__name__
                time.sleep(min(60, 4 * (attempt + 1)))
        return "", {}, 0.0, "failed:" + str(last)

    def _run_batch(self, event, header, b):
        user = header + "\n" + "\n\n".join(passage_block(i + 1, p) for i, p in enumerate(b))
        try:
            content, usage, secs, status = self._call(SYSTEM, user)
        except urllib.error.HTTPError as e:
            # HTTP 400 (the gateway rejected the request, seen on 3 of 1,485 events): judge the halves
            # separately; a single passage that is still rejected stays unjudged and sorts last.
            if e.code != 400:
                raise
            if len(b) > 1:
                self._run_batch(event, header, b[:len(b) // 2])
                self._run_batch(event, header, b[len(b) // 2:])
            else:
                with self.lock:
                    self.db.execute("INSERT INTO requests VALUES (?,?,?,?,?,?,?,?)", (self.model, event, 1, 0.0, None, None, "rejected:400", time.time()))
                    self.db.commit()
            return
        labels = parse_labels(content, len(b))
        if any(l is None for l in labels) and status == "ok":  # one retry for a malformed answer
            content, usage2, secs2, status = self._call(SYSTEM, user)
            labels = parse_labels(content, len(b))
            secs += secs2
        with self.lock:
            self.n_requests += 1
            self.db.execute("INSERT INTO requests VALUES (?,?,?,?,?,?,?,?)",
                            (self.model, event, len(b), secs, usage.get("prompt_tokens"), usage.get("completion_tokens"), status, time.time()))
            for p, l in zip(b, labels):
                if l:
                    self.db.execute("INSERT OR REPLACE INTO judgements VALUES (?,?,?,?,?,?)",
                                    (self.model, event, p["window_id"], PROMPT_VERSION, l, time.time()))
            self.db.commit()

    def submit(self, pool, event, ev, passages):
        """Queue the uncached batches of one event on `pool`; returns the futures. Read the labels
        with labels_for() once they are done. Lets the caller gather the next event meanwhile."""
        todo = [p for p in passages if self.cached(event, p["window_id"]) is None]
        self.n_cached += len(passages) - len(todo)
        header = event_header(ev)
        return [pool.submit(self._run_batch, event, header, todo[i:i + self.batch]) for i in range(0, len(todo), self.batch)]

    def labels_for(self, event, passages):
        return {p["window_id"]: self.cached(event, p["window_id"]) for p in passages}

    def judge_event(self, event, ev, passages):
        """passages: list of dicts with window_id plus passage_block fields. Returns {window_id: label}."""
        with ThreadPoolExecutor(self.workers) as ex:
            for f in self.submit(ex, event, ev, passages):
                f.result()
        return self.labels_for(event, passages)

    def stats(self):
        r = self.db.execute("SELECT count(*), sum(seconds), sum(prompt_tokens), sum(completion_tokens), "
                            "sum(status!='ok'), min(ts), max(ts) FROM requests WHERE model=?", (self.model,)).fetchone()
        return {"requests": r[0], "request_seconds": r[1], "prompt_tokens": r[2], "completion_tokens": r[3], "failed": r[4],
                "first": r[5], "last": r[6]}


def rerank(passages, labels):
    """passages in fused order; yes first, then mention, then no (unjudged last), fused order as the tie-break."""
    return [p for _, p in sorted(enumerate(passages), key=lambda ip: (LABEL_RANK.get(labels.get(ip[1]["window_id"]), 3), ip[0]))]
