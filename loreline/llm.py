"""Pluggable LLM backends using only the standard library.

Supported providers:
  * ollama     – local models (default when an Ollama server is reachable)
  * openai     – any OpenAI-compatible endpoint (OpenAI, LM Studio, llama.cpp, vLLM, Groq, OpenRouter, ...)
  * anthropic  – Claude models
  * none       – no LLM; loreline still works and prints the raw evidence
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


class LLMError(RuntimeError):
    pass


class LLM:
    name = "none"
    model = ""

    def available(self) -> bool:
        return False

    def complete(self, system: str, prompt: str) -> str:  # pragma: no cover
        raise LLMError("no LLM configured")


def _post(url: str, payload: dict, headers: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise LLMError(f"{url} returned HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise LLMError(f"could not reach {url}: {exc}") from exc


class Ollama(LLM):
    name = "ollama"

    def __init__(self, model: str, base_url: str, temperature: float, timeout: float):
        self.base_url = (base_url or os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434").rstrip("/")
        if not self.base_url.startswith("http"):
            self.base_url = "http://" + self.base_url
        self.model = model or "llama3.2"
        self.temperature = temperature
        self.timeout = timeout

    def available(self) -> bool:
        try:
            with urllib.request.urlopen(self.base_url + "/api/tags", timeout=1.5) as resp:
                tags = json.loads(resp.read().decode())
            names = [m.get("name", "") for m in tags.get("models", [])]
            if names and not any(n.split(":")[0] == self.model.split(":")[0] for n in names):
                self.model = names[0]
            return bool(names)
        except Exception:  # noqa: BLE001
            return False

    def complete(self, system: str, prompt: str) -> str:
        data = _post(self.base_url + "/api/chat", {
            "model": self.model, "stream": False, "options": {"temperature": self.temperature},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        }, {}, self.timeout)
        return data.get("message", {}).get("content", "").strip()


class OpenAICompat(LLM):
    name = "openai"

    def __init__(self, model: str, base_url: str, api_key: str, temperature: float, timeout: float):
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model or "gpt-4o-mini"
        self.temperature = temperature
        self.timeout = timeout

    def available(self) -> bool:
        return bool(self.api_key) or "localhost" in self.base_url or "127.0.0.1" in self.base_url

    def complete(self, system: str, prompt: str) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        data = _post(self.base_url + "/chat/completions", {
            "model": self.model, "temperature": self.temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        }, headers, self.timeout)
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError) as exc:
            raise LLMError(f"unexpected response: {str(data)[:300]}") from exc


class Anthropic(LLM):
    name = "anthropic"

    def __init__(self, model: str, base_url: str, api_key: str, temperature: float, timeout: float):
        self.base_url = (base_url or "https://api.anthropic.com").rstrip("/")
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model or "claude-sonnet-5-5"
        self.temperature = temperature
        self.timeout = timeout

    def available(self) -> bool:
        return bool(self.api_key)

    def complete(self, system: str, prompt: str) -> str:
        data = _post(self.base_url + "/v1/messages", {
            "model": self.model, "max_tokens": 1500, "temperature": self.temperature, "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }, {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"}, self.timeout)
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()


def from_config(cfg: dict) -> LLM:
    c = cfg.get("llm", {})
    provider = (c.get("provider") or "auto").lower()
    model, base, key = c.get("model", ""), c.get("base_url", ""), c.get("api_key", "")
    temp, timeout = float(c.get("temperature", 0.2)), float(c.get("timeout", 120))
    if provider == "none":
        return LLM()
    if provider == "ollama":
        return Ollama(model, base, temp, timeout)
    if provider in ("openai", "openai-compatible", "lmstudio", "llamacpp", "vllm"):
        return OpenAICompat(model, base, key, temp, timeout)
    if provider in ("anthropic", "claude"):
        return Anthropic(model, base, key, temp, timeout)
    # auto: prefer local, then hosted keys from the environment.
    local = Ollama(model, base, temp, timeout)
    if local.available():
        return local
    if os.environ.get("ANTHROPIC_API_KEY"):
        return Anthropic(model, "", "", temp, timeout)
    if os.environ.get("OPENAI_API_KEY"):
        return OpenAICompat(model, "", "", temp, timeout)
    return LLM()
