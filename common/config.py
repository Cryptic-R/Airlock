"""Central configuration. Everything comes from environment variables (.env)."""

import os

from dotenv import find_dotenv, load_dotenv
from uagents_core.identity import Identity

from pathlib import Path
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


ORCHESTRATOR_SEED = os.getenv("ORCHESTRATOR_SEED_PHRASE", "airlock-orchestrator-change-me")
READER_SEED = os.getenv("READER_SEED_PHRASE", "airlock-reader-change-me")
BANK_SEED = os.getenv("BANK_SEED_PHRASE", "airlock-bank-change-me")

ORCHESTRATOR_PORT = int(os.getenv("ORCHESTRATOR_PORT", "8010"))
READER_PORT = int(os.getenv("READER_PORT", "8011"))
BANK_PORT = int(os.getenv("BANK_PORT", "8012"))

ORCHESTRATOR_ADDRESS = Identity.from_seed(seed=ORCHESTRATOR_SEED, index=0).address
READER_ADDRESS = Identity.from_seed(seed=READER_SEED, index=0).address
BANK_ADDRESS = Identity.from_seed(seed=BANK_SEED, index=0).address

# ASI:One LLM (OpenAI-compatible) -- used as the (untrusted-content) planner.
ASI1_API_KEY = os.getenv("ASI1_API_KEY", "")
ASI1_BASE_URL = os.getenv("ASI1_BASE_URL", "https://api.asi1.ai/v1")
ASI1_MODEL = os.getenv("ASI1_MODEL", "asi1")

HELPER_TIMEOUT_S = float(os.getenv("HELPER_TIMEOUT_S", "30"))

# Payment Protocol: an approved bill is settled in FET (testnet by default).
ENABLE_PAYMENTS = _bool("ENABLE_PAYMENTS", "false")
# Price is per-FET display; the approved bill's own amount drives the request.
FET_USE_TESTNET = _bool("FET_USE_TESTNET", "true")
# Demo settlement rate: 1 currency unit of a bill -> this many FET (keeps testnet amounts tiny).
BILL_TO_FET = float(os.getenv("BILL_TO_FET", "0.001"))
