"""Minimal LLM client with a content-addressed disk cache.

Backends
--------
* ``openrouter``  - HTTPS call to openrouter.ai (needs OPENROUTER_API_KEY).
* ``claude-cli``  - the locally installed Claude Code CLI in headless print mode with all
                    tools disabled, a custom system prompt and no session persistence.

Every response is cached under data/cache/llm/<sha256>.json together with the model,
prompt hash and timestamp, so `python run.py` reproduces the submission offline and every
rule can be traced to the exact model call that produced it (see audit_log.jsonl).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from . import config

_lock = threading.Lock()
_stats = {"calls": 0, "cache_hits": 0, "failures": 0}
_used: set[str] = set()      # cache keys touched in this process (for --prune-cache)


class LLMError(RuntimeError):
    pass


def _load_dotenv() -> None:
    env = config.ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


def backend() -> str:
    b = os.environ.get("LEXMAP_LLM_BACKEND", config.LLM_BACKEND)
    if b != "auto":
        return b
    if os.environ.get("OPENROUTER_API_KEY"):
        return "openrouter"
    if shutil.which("claude"):
        return "claude-cli"
    return "cache-only"


def prompt_hash(model: str, system: str, prompt: str) -> str:
    h = hashlib.sha256()
    for part in (model, "\x00", system, "\x00", prompt):
        h.update(part.encode("utf-8"))
    return h.hexdigest()


def _cache_path(key: str) -> Path:
    return config.LLM_CACHE / f"{key}.json"


def _call_openrouter(model: str, system: str, prompt: str, timeout: int) -> str:
    import requests
    mid = config.OPENROUTER_MODELS.get(model, model)
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                 "Content-Type": "application/json",
                 "X-Title": "Lexmap"},
        json={"model": mid, "temperature": 0,
              "messages": [{"role": "system", "content": system},
                           {"role": "user", "content": prompt}]},
        timeout=timeout,
    )
    if r.status_code != 200:
        raise LLMError(f"openrouter {r.status_code}: {r.text[:300]}")
    return r.json()["choices"][0]["message"]["content"]


def _call_claude_cli(model: str, system: str, prompt: str, timeout: int) -> str:
    exe = shutil.which("claude")
    if not exe:
        raise LLMError("claude CLI not found")
    cwd = tempfile.mkdtemp(prefix="lexmap_llm_")
    cmd = [exe, "-p", "--output-format", "json", "--model", model,
           "--system-prompt", system, "--tools", "", "--no-session-persistence",
           "--strict-mcp-config", "--setting-sources", ""]
    p = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                       timeout=timeout, encoding="utf-8", cwd=cwd)
    if p.returncode != 0:
        raise LLMError(f"claude-cli rc={p.returncode}: {p.stderr[:300]} {p.stdout[:300]}")
    try:
        j = json.loads(p.stdout)
    except json.JSONDecodeError as e:
        raise LLMError(f"claude-cli non-json stdout: {p.stdout[:300]}") from e
    if j.get("is_error"):
        raise LLMError(f"claude-cli error: {str(j.get('result'))[:300]}")
    return j.get("result") or ""


def complete(prompt: str, system: str, model: str | None = None, *, use_cache: bool = True,
             timeout: int = 900, retries: int = 3, tag: str = "") -> dict:
    """Return {'text', 'model', 'key', 'cached', 'created_at', 'backend'}."""
    model = model or config.EXTRACT_MODEL
    key = prompt_hash(model, system, prompt)
    with _lock:
        _used.add(key)
    cp = _cache_path(key)
    if use_cache and cp.exists():
        with _lock:
            _stats["cache_hits"] += 1
        rec = json.loads(cp.read_text(encoding="utf-8"))
        rec["cached"] = True
        return rec
    be = backend()
    if be == "cache-only":
        raise LLMError("No LLM backend available and response not cached. Set OPENROUTER_API_KEY "
                       "or install the Claude Code CLI.")
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with _lock:
                _stats["calls"] += 1
            if be == "openrouter":
                text = _call_openrouter(model, system, prompt, timeout)
            else:
                text = _call_claude_cli(model, system, prompt, timeout)
            rec = {"key": key, "model": model, "backend": be, "tag": tag,
                   "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "text": text}
            config.LLM_CACHE.mkdir(parents=True, exist_ok=True)
            cp.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
            rec["cached"] = False
            return rec
        except Exception as e:  # noqa: BLE001 - retry any transport failure
            last = e
            with _lock:
                _stats["failures"] += 1
            wait = 20 * (attempt + 1)
            if "limit" in str(e).lower() or "usage" in str(e).lower():
                wait = 300 * (attempt + 1)
            time.sleep(wait)
    raise LLMError(f"LLM call failed after {retries} attempts: {last}")


def complete_json(prompt: str, system: str, model: str | None = None, **kw) -> tuple[object, dict]:
    """complete() and parse the first JSON value in the reply. Retries once with a nudge."""
    rec = complete(prompt, system, model, **kw)
    try:
        return parse_json(rec["text"]), rec
    except ValueError:
        # Bad cache entry or malformed reply: ask again with an explicit reminder.
        rec = complete(prompt + "\n\nReturn ONLY valid JSON. No prose, no markdown fences.",
                       system, model, **kw)
        return parse_json(rec["text"]), rec


def parse_json(text: str):
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    starts = [i for i in (t.find("{"), t.find("[")) if i >= 0]
    if not starts:
        raise ValueError("no JSON in reply")
    s = min(starts)
    closer = "}" if t[s] == "{" else "]"
    e = t.rfind(closer)
    if e <= s:
        raise ValueError("unterminated JSON in reply")
    return json.loads(t[s:e + 1])


def stats() -> dict:
    return dict(_stats)


def prune_cache() -> int:
    """Delete cached responses not used by this run (stale prompts from earlier iterations)."""
    n = 0
    for f in config.LLM_CACHE.glob("*.json"):
        if f.stem in _used:
            continue
        try:
            tag = json.loads(f.read_text(encoding="utf-8")).get("tag", "")
        except (OSError, ValueError):
            tag = ""
        if tag.startswith("whatif"):
            continue              # what-if demos are run separately; keep them reproducible
        f.unlink()
        n += 1
    return n
