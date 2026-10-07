"""
LLM transport for the Presentation & Prediction Layer.

Deliberately kept API-compatible with Member 1's `llm.py` (same provider
switch, same token-stats contract) so the two components can share one .env.

Two differences matter for this component:

  1. `call_llm_json()` enforces a JSON-object response. Query understanding is
     a *structured extraction* task, not free text, so we request JSON mode
     where the provider supports it and repair-parse where it does not.

  2. `LLM_PROVIDER=none` is a first-class mode. Every research metric in
     `evaluate.py` must be reproducible on a machine with no API key, so the
     analyzer always has a deterministic fallback path (see query_analyzer.py).
"""

import json
import os
import re
import time

from profiler import log_step, time_block

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - dotenv is optional
    pass

PROVIDER = os.getenv("LLM_PROVIDER", "none").lower().strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

_gemini_client = None
_groq_client = None


class LLMUnavailable(RuntimeError):
    """Raised when no provider is configured, or the provider cannot be reached."""


def active_model() -> str:
    if PROVIDER == "gemini":
        return GEMINI_MODEL
    if PROVIDER == "groq":
        return GROQ_MODEL
    return "deterministic-fallback"


def is_available() -> bool:
    """True when a provider is configured AND its API key is present."""
    if PROVIDER == "groq":
        return bool(os.getenv("GROQ_API_KEY"))
    if PROVIDER == "gemini":
        return bool(os.getenv("GEMINI_API_KEY"))
    return False


def get_client():
    global _gemini_client, _groq_client

    if PROVIDER == "gemini":
        if _gemini_client is None:
            key = os.getenv("GEMINI_API_KEY")
            if not key:
                raise LLMUnavailable("GEMINI_API_KEY is not set in .env")
            from google import genai

            _gemini_client = genai.Client(api_key=key)
        return _gemini_client

    if PROVIDER == "groq":
        if _groq_client is None:
            key = os.getenv("GROQ_API_KEY")
            if not key:
                raise LLMUnavailable("GROQ_API_KEY is not set in .env")
            from groq import Groq

            _groq_client = Groq(api_key=key)
        return _groq_client

    raise LLMUnavailable(f"No usable LLM_PROVIDER configured (got '{PROVIDER}')")


# --------------------------------------------------------------------------
# JSON extraction
# --------------------------------------------------------------------------

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_json(raw: str) -> dict:
    """
    Parse a JSON object out of a model response.

    Handles the three failure shapes we observed in practice: clean JSON,
    JSON wrapped in a markdown fence, and JSON preceded by a prose preamble.
    Raises ValueError if no object can be recovered.
    """
    if not raw or not raw.strip():
        raise ValueError("Empty LLM response")

    text = raw.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fence = _FENCE_RE.search(text)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Fall back to the widest balanced {...} span in the response.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not recover a JSON object from response: {text[:200]}...")


# --------------------------------------------------------------------------
# Transport
# --------------------------------------------------------------------------


def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    retries: int = 3,
    profiler=None,
    temperature: float = 0.0,
) -> tuple:
    """
    Execute a structured-output LLM request.

    Returns:
        tuple[dict, dict]: (parsed_json, token_stats)

    Raises:
        LLMUnavailable: no provider/key configured.
        ValueError:     provider responded but no JSON could be parsed.
    """
    client = get_client()
    model = active_model()
    categories = profiler.categories if profiler else None

    attempt = 0
    backoff = 1.0
    last_error = None

    while attempt < retries:
        attempt += 1
        try:
            with time_block(
                f"LLM Call ({PROVIDER.upper()} - {model}, attempt {attempt}/{retries})",
                parent_summary=categories,
                category="LLM API Inference",
            ):
                if PROVIDER == "gemini":
                    from google.genai import types

                    response = client.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=f"{system_prompt}\n\n{user_prompt}",
                        config=types.GenerateContentConfig(
                            temperature=temperature,
                            response_mime_type="application/json",
                        ),
                    )
                    raw = (response.text or "").strip()
                    usage = getattr(response, "usage_metadata", None)
                    prompt_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
                    completion_tokens = (
                        getattr(usage, "candidates_token_count", 0) if usage else 0
                    )
                    total_tokens = (
                        getattr(usage, "total_token_count", 0)
                        if usage
                        else prompt_tokens + completion_tokens
                    )

                else:  # groq
                    response = client.chat.completions.create(
                        model=GROQ_MODEL,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=temperature,
                        response_format={"type": "json_object"},
                    )
                    raw = (
                        response.choices[0].message.content.strip()
                        if response.choices
                        else ""
                    )
                    usage = getattr(response, "usage", None)
                    prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
                    completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
                    total_tokens = (
                        getattr(usage, "total_tokens", 0)
                        if usage
                        else prompt_tokens + completion_tokens
                    )

                parsed = extract_json(raw)

                token_stats = {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "model": model,
                    "provider": PROVIDER,
                    "attempts": attempt,
                }
                log_step(
                    f"LLM JSON call OK | tokens: {prompt_tokens} in / "
                    f"{completion_tokens} out / {total_tokens} total"
                )
                return parsed, token_stats

        except Exception as exc:  # noqa: BLE001 - retried and re-raised below
            last_error = exc
            log_step(f"LLM call attempt {attempt}/{retries} failed: {exc}", level="WARN")
            if attempt >= retries:
                break
            time.sleep(backoff)
            backoff *= 2.0

    log_step(f"All {retries} LLM attempts failed.", level="ERROR")
    raise last_error if last_error else RuntimeError("LLM execution failed")
