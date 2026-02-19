"""
llm/gemini_client.py — LLM client wrapper.

Supports three providers:
  - "groq"   : Groq Cloud API — free, fast, 14,400 req/day (RECOMMENDED)
  - "gemini" : Google Gemini API — free tier currently broken in India
  - "ollama" : Local Ollama server — free, offline fallback

Switching providers requires ONE line change in config.py:
    LLM_PROVIDER = "groq"

Why a wrapper instead of calling the SDK directly?
  Every other module calls call_llm(prompt) — they don't know or care
  which provider is being used. This makes the system genuinely swappable.
"""

import config
from logger import log


def call_llm(prompt: str) -> str:
    """
    Send a prompt to the configured LLM and return the response text.

    Args:
        prompt: The complete prompt string (built by prompts.py)

    Returns:
        The model's response as a plain string.

    Raises:
        RuntimeError if the API call fails.
    """
    if config.LLM_PROVIDER == "groq":
        return _call_groq(prompt)
    elif config.LLM_PROVIDER == "gemini":
        return _call_gemini(prompt)
    elif config.LLM_PROVIDER == "ollama":
        return _call_ollama(prompt)
    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER: '{config.LLM_PROVIDER}'. "
            f"Must be 'groq', 'gemini', or 'ollama'."
        )


# ── Groq ──────────────────────────────────────────────────────────────────────

def _call_groq(prompt: str) -> str:
    """
    Call Groq Cloud API — free tier, 14,400 requests/day, no credit card.

    Groq uses the same interface as OpenAI's SDK, so this is very simple.
    Get a free key at: https://console.groq.com

    Model used: llama-3.3-70b-versatile — excellent at SQL generation.
    """
    try:
        from groq import Groq

        if not config.GROQ_API_KEY:
            raise ValueError(
                "GROQ_API_KEY is not set. "
                "Add it to your .env file: GROQ_API_KEY=your_key_here\n"
                "Get a free key at: https://console.groq.com"
            )

        client = Groq(api_key=config.GROQ_API_KEY)

        log("LLM_CALL", f"Groq [{config.GROQ_MODEL}] prompt length: {len(prompt)} chars")

        response = client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,      # deterministic — we want consistent SQL
            max_tokens=512,
        )

        result = response.choices[0].message.content.strip()
        log("LLM_RESPONSE", f"Groq response: {result[:200]}")
        return result

    except Exception as e:
        log("LLM_ERROR", f"Groq error: {e}")
        raise RuntimeError(f"Groq API call failed: {e}") from e


# ── Gemini ────────────────────────────────────────────────────────────────────

def _call_gemini(prompt: str) -> str:
    """
    Call Google Gemini API.
    Note: Free tier currently has zero quota for gemini-2.0-flash in many regions.
    Switch to LLM_PROVIDER = "groq" for a working free alternative.
    """
    try:
        import google.generativeai as genai

        if not config.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY is not set. "
                "Add it to your .env file: GEMINI_API_KEY=your_key_here"
            )

        genai.configure(api_key=config.GEMINI_API_KEY)
        model = genai.GenerativeModel(config.GEMINI_MODEL)

        log("LLM_CALL", f"Gemini [{config.GEMINI_MODEL}] prompt length: {len(prompt)} chars")

        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.0,
                max_output_tokens=512,
            ),
        )

        result = response.text.strip()
        log("LLM_RESPONSE", f"Gemini response: {result[:200]}")
        return result

    except Exception as e:
        log("LLM_ERROR", f"Gemini error: {e}")
        raise RuntimeError(f"Gemini API call failed: {e}") from e


# ── Ollama ────────────────────────────────────────────────────────────────────

def _call_ollama(prompt: str) -> str:
    """
    Call a local Ollama model — completely free and offline.
    Install from https://ollama.com then run: ollama pull llama3.2:3b
    """
    try:
        import requests

        url = f"{config.OLLAMA_BASE_URL}/api/generate"
        payload = {
            "model":  config.OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 512},
        }

        log("LLM_CALL", f"Ollama [{config.OLLAMA_MODEL}] prompt length: {len(prompt)} chars")

        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()

        result = response.json()["response"].strip()
        log("LLM_RESPONSE", f"Ollama response: {result[:200]}")
        return result

    except Exception as e:
        log("LLM_ERROR", f"Ollama error: {e}")
        raise RuntimeError(
            f"Ollama API call failed: {e}\n"
            "Make sure Ollama is running: https://ollama.com"
        ) from e
