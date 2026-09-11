"""Central config. Everything comes from .env; nothing is hard-coded."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

HOTDATA_API_URL = os.getenv("HOTDATA_API_URL", "https://api.hotdata.dev/v1").rstrip("/")
HOTDATA_API_KEY = os.getenv("HOTDATA_API_KEY", "")
HOTDATA_WORKSPACE_ID = os.getenv("HOTDATA_WORKSPACE_ID", "")

ROCKETRIDE_URI = os.getenv("ROCKETRIDE_URI", "https://api.rocketride.ai")
ROCKETRIDE_AUTH = os.getenv("ROCKETRIDE_AUTH", "")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

TELEMETRY_DB_NAME = os.getenv("TELEMETRY_DB_NAME", "responsegrid_telemetry")
TELEMETRY_DB_ID = os.getenv("TELEMETRY_DB_ID", "")
TELEMETRY_CONNECTION_ID = os.getenv("TELEMETRY_CONNECTION_ID", "")
TELEMETRY_SCHEMA = "main"

# Bumped by hand when we change agent config, so telemetry can compare before/after.
CONFIG_VERSION = os.getenv("CONFIG_VERSION", "v3")

SPECIALIST_PROFILE = os.getenv("SPECIALIST_PROFILE", "claude-haiku-4-5")
COMMANDER_PROFILE = os.getenv("COMMANDER_PROFILE", "claude-sonnet-4-6")
MAX_WAVES = int(os.getenv("MAX_WAVES", "4"))
ENGINE_THREADS = int(os.getenv("ENGINE_THREADS", "16"))
AGENT_TIMEOUT_S = float(os.getenv("AGENT_TIMEOUT_S", "90"))

# Published per-MTok rates, used only to derive an estimate from measured token counts.
MODEL_RATES = {
    "claude-haiku-4-5":  {"in": 1.00, "out": 5.00},
    "claude-sonnet-4-6": {"in": 3.00, "out": 15.00},
    "claude-opus-4-6":   {"in": 15.00, "out": 75.00},
}

def estimate_cost(model: str, tok_in: int, tok_out: int) -> float:
    r = MODEL_RATES.get(model)
    if not r:
        return 0.0
    return round(tok_in / 1e6 * r["in"] + tok_out / 1e6 * r["out"], 6)

def missing() -> list[str]:
    out = []
    if not HOTDATA_API_KEY: out.append("HOTDATA_API_KEY")
    if not HOTDATA_WORKSPACE_ID: out.append("HOTDATA_WORKSPACE_ID")
    if not ROCKETRIDE_AUTH and "localhost" not in ROCKETRIDE_URI: out.append("ROCKETRIDE_AUTH")
    if not ANTHROPIC_API_KEY: out.append("ANTHROPIC_API_KEY")
    return out
