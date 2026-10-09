"""One Claude client wrapper for the whole harness.

- Structured output: output_config.format = json_schema (anthropic 1.8.0 exposes it on messages.create); if the API
  rejects the schema, the same request is retried once asking for JSON in the prompt, and the reply is parsed.
- Cache: responses are stored under <state>/llm_cache/<sha256 of the request>.json, so re-running a step never pays
  twice for the same document inside one state dir.
- Retries: our own loop (SDK retries off) with exponential backoff and jitter on 429, 529/overloaded, 5xx, timeouts and
  connection errors, honouring retry-after, and never starting an attempt that cannot finish before the step deadline.
- Refusal: retried once on the other configured model.
The key and base URL come from ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL (read by the SDK); nothing is stored.
"""
from __future__ import annotations

import base64
import hashlib
import json
import random
import threading
import time
from pathlib import Path

import config

from . import spend
from .prompt_versions import version_tag
_SLOTS = threading.BoundedSemaphore(max(1, config.LLM_THREADS))   # global cap on concurrent API calls


class BudgetExceeded(Exception):
    """The step deadline is too close to start (or retry) a model call."""


class LLMError(Exception):
    pass


class Budget:
    def __init__(self, seconds: float):
        self.start = time.monotonic()
        self.deadline = self.start + seconds

    def remaining(self) -> float:
        return self.deadline - time.monotonic()

    def elapsed(self) -> float:
        return time.monotonic() - self.start


class LLM:
    def __init__(self, state, budget: Budget):
        self.state = state
        self.budget = budget
        self.cache_dir = Path(state.dir) / "llm_cache"
        self._client = None
        self._lock = threading.Lock()
        self.usage = {"calls": 0, "cached": 0, "input": 0, "output": 0, "cache_read": 0, "cache_write": 0}

    @property
    def client(self):
        with self._lock:
            if self._client is None:
                import os

                import anthropic
                if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
                    raise BudgetExceeded("no ANTHROPIC_API_KEY in the environment: documents stay pending")
                # An organisation-level key needs the workspace named on every request.
                ws = os.environ.get("ANTHROPIC_WORKSPACE_ID") or os.environ.get("NOVA_WORKSPACE_ID")
                extra = {"default_headers": {"anthropic-workspace-id": ws}} if ws else {}
                self._client = anthropic.Anthropic(max_retries=0, timeout=config.LLM_REQUEST_TIMEOUT_S, **extra)
            return self._client

    # ---- public ----------------------------------------------------------------------------------------------------
    def json_call(self, *, model: str, system: str, blocks: list[dict], schema: dict, effort: str,
                  max_tokens: int, purpose: str, cache_doc_block: bool = False) -> dict:
        """-> parsed JSON object. `blocks` is the user content (text/image blocks); the last text block is the
        document. cache_doc_block marks the first block with cache_control (shared contract text)."""
        version = version_tag(purpose)
        key = self.cache_key(model, version, system, blocks, schema, effort)
        hit = self._cache_get(key)
        if hit is not None and hit.get("requested_model", model) == model and \
                hit.get("prompt_version", version) == version:
            with self._lock:
                self.usage["cached"] += 1
            return hit["data"]
        try:
            data, resp_model, usage = self._call(model, system, blocks, schema, effort, max_tokens, cache_doc_block)
        except _Refused:
            other = config.MODEL_DOC if model == config.MODEL_CONTRACT else config.MODEL_CONTRACT
            data, resp_model, usage = self._call(other, system, blocks, schema, effort, max_tokens, cache_doc_block)
        self._cache_put(key, {"data": data, "model": resp_model, "requested_model": model, "prompt_version": version,
                              "content_sha256": _content_hash(blocks), "usage": usage, "purpose": purpose})
        self.state.log("llm_usage.jsonl", {"purpose": purpose, "model": resp_model, **usage})
        return data

    # ---- internals ---------------------------------------------------------------------------------------------------
    @staticmethod
    def cache_key(model: str, version: str, system: str, blocks: list[dict], schema: dict, effort: str) -> str:
        """sha256 over: prompt version of this extraction kind, model, effort, system prompt, schema, and every content
        block (instructions + the document text, or the image's hash). Same document + model + prompt -> same key."""
        h = hashlib.sha256()
        for part in (version, model, effort, system, json.dumps(schema, sort_keys=True)):
            h.update(part.encode())
            h.update(b"\x00")
        for b in blocks:
            h.update(json.dumps(b, sort_keys=True).encode() if b.get("type") != "image"
                     else hashlib.sha256(b["source"]["data"].encode()).digest())
        return h.hexdigest()

    def _dirs(self) -> list[Path]:
        dirs = [self.cache_dir]
        if config.CACHE_DIR:                       # dev only: share extractions across runs, modes and state dirs
            d = Path(config.CACHE_DIR).expanduser()
            d.mkdir(parents=True, exist_ok=True)
            dirs.append(d)
        return dirs

    def _cache_get(self, key: str):
        for d in self._dirs():
            f = d / f"{key}.json"
            if f.is_file():
                try:
                    hit = json.loads(f.read_text())
                except json.JSONDecodeError:
                    continue
                if d != self.cache_dir:
                    self._write(self.cache_dir, key, hit)
                return hit
        return None

    def _cache_put(self, key: str, value: dict) -> None:
        for d in self._dirs():
            self._write(d, key, value)

    @staticmethod
    def _write(d: Path, key: str, value: dict) -> None:
        tmp = d / f"{key}.json.{threading.get_ident()}.tmp"
        tmp.write_text(json.dumps(value))
        tmp.replace(d / f"{key}.json")

    def _call(self, model, system, blocks, schema, effort, max_tokens, cache_doc_block):
        import anthropic
        content = [dict(b) for b in blocks]
        if cache_doc_block and content:
            content[0] = {**content[0], "cache_control": {"type": "ephemeral"}}
        params = dict(model=model, max_tokens=max_tokens,
                      system=[{"type": "text", "text": system}],
                      messages=[{"role": "user", "content": content}],
                      output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}})
        if model in config.THINKING_OFF_MODELS:
            params["thinking"] = {"type": "between_tools"}
        schema_in_prompt = False
        attempt = 0
        while True:
            attempt += 1
            remaining = self.budget.remaining()
            if remaining < 15:
                raise BudgetExceeded(f"{remaining:.0f}s left")
            if spend.over_limit():
                raise BudgetExceeded(f"spend limit reached (${spend.total():.2f}); documents stay pending")
            try:
                with _SLOTS:
                    resp = self.client.with_options(timeout=min(config.LLM_REQUEST_TIMEOUT_S, remaining - 5)) \
                        .messages.create(**params)
                with self._lock:
                    self.usage["calls"] += 1
                u = resp.usage
                usage = {"input": u.input_tokens, "output": u.output_tokens,
                         "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0,
                         "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0}
                spend.record(resp.model or model, usage, "llm")
                if resp.stop_reason == "refusal":
                    raise _Refused()
                text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
                if resp.stop_reason == "max_tokens":
                    raise LLMError(f"hit max_tokens ({max_tokens})")
                data = _parse_json(text)
                with self._lock:
                    for k, v in usage.items():
                        self.usage[k] += v
                return data, resp.model, usage
            except _Refused:
                raise
            except anthropic.BadRequestError as e:
                msg = str(e).lower()
                if "thinking" in params and "thinking" in msg:
                    params.pop("thinking")                 # this model/effort doesn't take it: use the default
                    continue
                if not schema_in_prompt and ("output_config" in msg or "schema" in msg or "format" in msg):
                    # fall back to JSON-in-prompt for schemas the structured-output compiler won't take
                    schema_in_prompt = True
                    params.pop("output_config")
                    params["output_config"] = {"effort": effort}
                    params["messages"][0]["content"] = content + [{"type": "text", "text": (
                        "Reply with one JSON object only (no prose, no code fence) matching this JSON schema:\n"
                        + json.dumps(schema))}]
                    continue
                raise LLMError(f"bad request: {e}") from e
            except (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError,
                    anthropic.APITimeoutError) as e:
                retry_after = None
                resp = getattr(e, "response", None)
                if resp is not None:
                    try:
                        retry_after = float(resp.headers.get("retry-after"))
                    except (TypeError, ValueError):
                        retry_after = None
                self._backoff(attempt, retry_after, e)
            except anthropic.APIStatusError as e:
                if getattr(e, "status_code", 0) in (408, 409, 429, 529) or getattr(e, "status_code", 0) >= 500:
                    self._backoff(attempt, None, e)
                else:
                    raise LLMError(f"API error {getattr(e, 'status_code', '?')}: {e}") from e
            except (json.JSONDecodeError, ValueError) as e:
                if attempt >= 2:
                    raise LLMError(f"unparseable reply: {e}") from e

    def _backoff(self, attempt: int, retry_after: float | None, err: Exception) -> None:
        if attempt >= config.LLM_MAX_ATTEMPTS:
            raise LLMError(f"gave up after {attempt} attempts: {type(err).__name__}: {err}") from err
        delay = retry_after if retry_after else min(config.LLM_BACKOFF_MAX_S,
                                                    config.LLM_BACKOFF_BASE_S * 2 ** (attempt - 1))
        delay += random.uniform(0, 1)
        if self.budget.remaining() - delay < 20:
            raise BudgetExceeded("no time left to retry") from err
        time.sleep(delay)


class _Refused(Exception):
    pass


def _content_hash(blocks: list[dict]) -> str:
    h = hashlib.sha256()
    for b in blocks:
        h.update(json.dumps(b, sort_keys=True).encode() if b.get("type") != "image"
                 else hashlib.sha256(b["source"]["data"].encode()).digest())
    return h.hexdigest()


def _parse_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    start = text.find("{")
    if start > 0:
        text = text[start:]
    return json.loads(text[: text.rfind("}") + 1] if "}" in text else text)


def text_block(text: str) -> dict:
    return {"type": "text", "text": text}


def image_block(png: bytes) -> dict:
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                        "data": base64.standard_b64encode(png).decode()}}
