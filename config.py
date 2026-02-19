"""
config.py — Central configuration for nl_insight.

All settings live here. Change database, model, or limits in one place.
Other modules import from here — they never hardcode values themselves.
"""

import os
from dotenv import load_dotenv

load_dotenv()


# ── Database ──────────────────────────────────────────────────────────────────

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/nl_insight"
)


# ── LLM Provider ──────────────────────────────────────────────────────────────
# Change this ONE line to switch providers. Nothing else needs to change.
#
#   "groq"   → Groq Cloud (FREE, 14,400 req/day) ← RECOMMENDED
#   "gemini" → Google Gemini (free tier broken in India as of Dec 2025)
#   "ollama" → Local Ollama (free, offline, needs install)

LLM_PROVIDER = "groq"


# ── Groq Settings (free, no credit card) ─────────────────────────────────────
# Get key at: https://console.groq.com

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = "llama-3.3-70b-versatile"


# ── Gemini Settings ───────────────────────────────────────────────────────────

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = "gemini-2.0-flash"


# ── Ollama Settings (local, offline fallback) ─────────────────────────────────

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL    = "llama3.2:3b"


# ── Query Safety ──────────────────────────────────────────────────────────────

QUERY_ROW_LIMIT = 500

BLOCKED_SQL_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP",
    "ALTER", "TRUNCATE", "CREATE", "REPLACE",
    "GRANT", "REVOKE", "EXEC", "EXECUTE",
]


# ── Logging ───────────────────────────────────────────────────────────────────

LOG_FILE = "logs/pipeline.log"


# ── App Display ───────────────────────────────────────────────────────────────

APP_TITLE = "NL Insight — Ask Your Data"
APP_ICON  = "🔍"
