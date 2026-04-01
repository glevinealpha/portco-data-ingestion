"""
AI provider abstraction layer.

Reads config.properties to decide whether to call Anthropic or AlphaGPT.
API keys can also be set via environment variables (ANTHROPIC_API_KEY / ALPHAGPT_API_KEY).

Usage:
    from pipeline.ai_client import complete
    text = complete("Summarise this: ...", max_tokens=300)
"""

import configparser
import os
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent.parent / "config.properties"

# ── Load config once at import time ───────────────────────────────────────────

_cfg = configparser.ConfigParser()
_cfg.read(str(_CONFIG_PATH))


def _get(section: str, key: str, env_var: str = "") -> str:
    """Read from config file, falling back to environment variable."""
    value = _cfg.get(section, key, fallback="").strip()
    if not value and env_var:
        value = os.environ.get(env_var, "")
    return value


PROVIDER    = _get("ai", "provider", "").lower() or "anthropic"

ANTHROPIC_KEY   = _get("anthropic", "api_key", "ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = _get("anthropic", "model", "") or "claude-sonnet-4-20250514"

ALPHAGPT_KEY      = _get("alphagpt", "api_key", "ALPHAGPT_API_KEY")
ALPHAGPT_BASE_URL = _get("alphagpt", "base_url", "") or "https://alphagpt.alphafmc.com/api/v1/"
ALPHAGPT_MODEL    = _get("alphagpt", "model", "") or "gpt-4o"


# ── Public interface ───────────────────────────────────────────────────────────

def complete(prompt: str, max_tokens: int = 1024) -> str:
    """
    Call the configured AI provider and return the response text.
    Raises RuntimeError if no API key is configured for the active provider.
    """
    if PROVIDER == "alphagpt":
        return _alphagpt_complete(prompt, max_tokens)
    return _anthropic_complete(prompt, max_tokens)


def active_provider() -> str:
    """Return the name of the currently configured provider."""
    return PROVIDER


# ── Provider implementations ───────────────────────────────────────────────────

def _anthropic_complete(prompt: str, max_tokens: int) -> str:
    if not ANTHROPIC_KEY:
        raise RuntimeError(
            "No Anthropic API key found. Set api_key in config.properties [anthropic] "
            "or the ANTHROPIC_API_KEY environment variable."
        )
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    msg = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def _alphagpt_complete(prompt: str, max_tokens: int) -> str:
    if not ALPHAGPT_KEY:
        raise RuntimeError(
            "No AlphaGPT API key found. Set api_key in config.properties [alphagpt] "
            "or the ALPHAGPT_API_KEY environment variable."
        )
    import openai
    client = openai.OpenAI(api_key=ALPHAGPT_KEY, base_url=ALPHAGPT_BASE_URL)
    response = client.chat.completions.create(
        model=ALPHAGPT_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()
